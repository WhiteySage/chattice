"""Pub/Sub pull runner: delivery, dedupe, ACK/NACK, answer routing (B3/B4/B7, F03)."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from chattice import Dispatcher, Router
from chattice.capabilities import ResponseCapabilities, ResponseCapability
from chattice.cards import Card, CardHeader, Dialog, Section, TextParagraph
from chattice.events import ActionEvent, MessageEvent
from chattice.idempotency import ClaimResult, MemoryIdempotencyStorage
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import (
    DIALOG_UNSUPPORTED_MESSAGE,
    PubSubPullRunner,
)


class FakePubSubMessage:
    """Minimal pubsub_v1 subscriber message double."""

    def __init__(
        self,
        data: str,
        *,
        message_id: str = "m-1",
        delivery_attempt: int = 0,
    ) -> None:
        self.data = data
        self.message_id = message_id
        self.delivery_attempt = delivery_attempt
        self.acked = False
        self.nacked = False

    def ack(self) -> None:
        self.acked = True

    def nack(self) -> None:
        self.nacked = True

    @property
    def exactly_one_terminal(self) -> bool:
        """F03 invariant: a delivery is NEVER both ACKed and NACKed."""
        return self.acked != self.nacked


class FailingStorage(MemoryIdempotencyStorage):
    """Memory storage with a switchable failure mode for one operation."""

    def __init__(self, *, fail_complete: bool = False, fail_claim: bool = False):
        super().__init__()
        self.fail_complete = fail_complete
        self.fail_claim = fail_claim

    async def complete(self, key: str, *, owner: str) -> None:
        if self.fail_complete:
            raise RuntimeError("complete down")
        await super().complete(key, owner=owner)

    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> ClaimResult:
        if self.fail_claim:
            raise RuntimeError("claim down")
        return await super().claim(key, owner=owner, lease_seconds=lease_seconds)


class RenewCountingStorage(MemoryIdempotencyStorage):
    def __init__(self) -> None:
        super().__init__()
        self.renew_calls = 0

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        self.renew_calls += 1
        return await super().renew(key, owner=owner, lease_seconds=lease_seconds)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _runner(
    dispatcher: Dispatcher,
    bot: Any = None,
    *,
    storage: Any = None,
    renew_interval: float | None = None,
    subscription: str = "projects/P/subscriptions/S",
) -> PubSubPullRunner:
    return PubSubPullRunner(
        dispatcher,
        subscription,
        bot=bot,
        idempotency_storage=storage,
        renew_interval=renew_interval,
    )


async def _always(event: object, context: object) -> bool:
    return True


def _message_payload(text: str = "ping") -> str:
    return json.dumps(
        {
            "type": "MESSAGE",
            "message": {"text": text},
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
        }
    )


def _action_payload() -> str:
    return json.dumps(
        {
            "type": "CARD_CLICKED",
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
            "message": {"name": "spaces/A/messages/M1", "sender": {"type": "BOT"}},
            "common": {"invokedFunction": "card.clicked"},
        }
    )


async def test_ping_answer_sent_via_bot_and_acked() -> None:
    router = Router()

    @router.message(_always)
    async def ping(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.acked and not message.nacked
    assert message.exactly_one_terminal
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert sent == [
        {
            "space": "spaces/A",
            "text": "pong",
            "card": None,
            "notify": None,
            "private_to": None,
            "attachments": None,
        }
    ]


async def test_streaming_pull_injects_empty_response_capabilities() -> None:
    router = Router()
    seen: list[ResponseCapabilities] = []

    @router.message()
    async def handler(
        message: MessageEvent, capabilities: ResponseCapabilities
    ) -> None:
        seen.append(capabilities)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.acked
    assert len(seen) == 1
    assert ResponseCapability.SYNC_RESPONSE not in seen[0]


async def test_card_answer_updates_clicked_bot_card() -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(event: ActionEvent) -> Card:
        assert event.message is not None  # identity parsed for Pub/Sub updates
        return Card(
            header=CardHeader(title="updated"),
            sections=[Section(widgets=[TextParagraph("x")])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    message = FakePubSubMessage(_action_payload())
    await runner._handle(message)

    assert message.acked
    updates = [args for kind, args in bot.calls if kind == "update_message"]
    assert len(updates) == 1
    assert updates[0]["name"] == "spaces/A/messages/M1"
    assert updates[0]["card"]["header"]["title"] == "updated"


async def test_dialog_answer_rejected_with_capability_message() -> None:
    router = Router()

    @router.action("card.clicked")
    async def dialog(event: ActionEvent) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    message = FakePubSubMessage(_action_payload())
    await runner._handle(message)

    assert message.acked  # retrying cannot succeed — delivery absorbed
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert sent[0]["text"] == DIALOG_UNSUPPORTED_MESSAGE


async def test_duplicate_delivery_is_absorbed() -> None:
    calls: list[str] = []
    router = Router()

    @router.message(_always)
    async def count(message: MessageEvent) -> str:
        calls.append(message.text)
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    await runner._handle(FakePubSubMessage(_message_payload(), message_id="m-1"))
    await runner._handle(FakePubSubMessage(_message_payload(), message_id="m-1"))

    assert calls == ["ping"]  # second delivery absorbed by the dedupe claim


async def test_handler_error_nacks_then_poison_acks() -> None:
    router = Router()

    @router.message(_always)
    async def broken(message: MessageEvent) -> str:
        raise RuntimeError("boom")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)

    retried = FakePubSubMessage(_message_payload(), delivery_attempt=1)
    await runner._handle(retried)
    assert retried.nacked and not retried.acked
    assert retried.exactly_one_terminal

    poisoned = FakePubSubMessage(_message_payload(), delivery_attempt=5)
    await runner._handle(poisoned)
    assert poisoned.acked and not poisoned.nacked
    assert poisoned.exactly_one_terminal


async def test_complete_failure_nacks_and_never_acks() -> None:
    """F03 probe: complete() raising must NOT leave the delivery ACKed."""
    router = Router()

    @router.message(_always)
    async def ok(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, MockBot(), storage=FailingStorage(fail_complete=True))

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.nacked and not message.acked  # at-least-once preserved


async def test_answer_failure_nacks() -> None:
    """Bot failure during the answer must nack (pre-completion failure)."""

    class ExplodingBot(MockBot):
        async def send_message(
            self,
            space: Any,
            text: str | None = None,
            **kwargs: Any,
        ) -> Any:
            raise RuntimeError("bot down")

    router = Router()

    @router.message(_always)
    async def answer(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, ExplodingBot())

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.nacked and not message.acked


async def test_claim_storage_failure_nacks() -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    runner = _runner(dispatcher, storage=FailingStorage(fail_claim=True))

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.nacked and not message.acked  # redelivery will retry


async def test_long_handler_renews_lease() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    router = Router()

    @router.message(_always)
    async def slow(message: MessageEvent) -> str:
        started.set()
        await release.wait()
        return "done"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    storage = RenewCountingStorage()
    runner = _runner(dispatcher, MockBot(), storage=storage, renew_interval=0.05)

    task = asyncio.create_task(runner._handle(FakePubSubMessage(_message_payload())))
    await started.wait()
    await asyncio.sleep(0.15)  # >= two renew intervals elapse
    assert storage.renew_calls >= 2  # the lease IS being renewed (F03)
    release.set()
    await task


async def test_same_message_id_in_two_subscriptions_both_processed() -> None:
    """F03 namespacing: the dedupe key includes the subscription."""
    calls: list[str] = []
    router = Router()

    @router.message(_always)
    async def count(message: MessageEvent) -> str:
        calls.append(message.text)
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    storage = MemoryIdempotencyStorage()
    runner_s = _runner(dispatcher, MockBot(), storage=storage)
    runner_t = _runner(
        dispatcher,
        MockBot(),
        storage=storage,
        subscription="projects/P/subscriptions/T",
    )

    await runner_s._handle(FakePubSubMessage(_message_payload(), message_id="m-1"))
    await runner_t._handle(FakePubSubMessage(_message_payload(), message_id="m-1"))

    assert calls == ["ping", "ping"]  # same ID, different subscriptions


async def test_expired_lease_takeover_survives_old_release() -> None:
    """F03: after a lease takeover, the OLD attempt's release must not
    drop the NEW owner's claim (owner-checked release)."""
    clock = FakeClock()
    storage = MemoryIdempotencyStorage(clock=clock)
    router = Router()

    @router.message(_always)
    async def ok(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, MockBot(), storage=storage)

    key = "projects/P/subscriptions/S:m-1"
    await storage.claim(key, owner="old-owner", lease_seconds=1.0)
    clock.now = 2.0  # the old lease expires

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)  # takeover -> FIRST -> processed -> completed

    await storage.release(key, owner="old-owner")  # must be a no-op

    result = await storage.claim(key, owner="probe", lease_seconds=1.0)
    assert result is ClaimResult.COMPLETED  # new claim still intact


async def test_poison_ack_notifies_best_effort_first() -> None:
    router = Router()

    @router.message(_always)
    async def broken(message: MessageEvent) -> str:
        raise RuntimeError("boom")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    poisoned = FakePubSubMessage(_message_payload(), delivery_attempt=5)
    await runner._handle(poisoned)

    assert poisoned.acked and not poisoned.nacked
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert len(sent) == 1
    assert "Error while processing" in sent[0]["text"]
    assert sent[0]["space"] == "spaces/A"


async def test_cancelled_handler_nacks() -> None:
    release = asyncio.Event()
    router = Router()

    @router.message(_always)
    async def stuck(message: MessageEvent) -> str:
        await release.wait()
        return "never"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)

    message = FakePubSubMessage(_message_payload())
    task = asyncio.create_task(runner._handle(message))
    await asyncio.sleep(0.05)
    task.cancel()
    with __import__("pytest").raises(asyncio.CancelledError):
        await task

    assert message.nacked and not message.acked


async def test_push_envelope_wire_shape_accepted() -> None:
    router = Router()

    @router.message(_always)
    async def echo(message: MessageEvent) -> str:
        return message.text

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    envelope = json.dumps(
        {
            "message": {
                "data": base64.b64encode(
                    _message_payload("via-envelope").encode()
                ).decode(),
                "messageId": "m-env",
            },
            "subscription": "projects/P/subscriptions/S",
        }
    )
    message = FakePubSubMessage(envelope, message_id="m-env")
    await runner._handle(message)

    assert message.acked
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert sent[0]["text"] == "via-envelope"


async def test_close_is_idempotent() -> None:
    dispatcher = Dispatcher()
    runner = _runner(dispatcher)
    await runner.close()
    await runner.close()  # second call must be a no-op
