"""Pub/Sub pull runner: delivery, dedupe, ACK/NACK, and answer routing."""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from chattice import Dispatcher, Router
from chattice.auth import CredentialsProvider
from chattice.capabilities import ResponseCapabilities, ResponseCapability
from chattice.cards import Card, CardHeader, Dialog, Section, TextParagraph
from chattice.events import ActionEvent, CommandEvent, MessageEvent, MessageRef
from chattice.exceptions import ChatticeError
from chattice.idempotency import ClaimResult, MemoryIdempotencyStorage
from chattice.testing import EventFactory, MockBot
from chattice.transports.pubsub import PubSubEnvelopeError
from chattice.transports.pubsub_runner import (
    DIALOG_UNSUPPORTED_MESSAGE,
    PubSubPullRunner,
    _event_context,
    _import_pubsub,
    _KeyedLockRegistry,
)


class FakePubSubMessage:
    """Minimal pubsub_v1 subscriber message double."""

    def __init__(
        self,
        data: Any,
        *,
        message_id: str = "m-1",
        delivery_attempt: int | None = 0,
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
        """A delivery is never both ACKed and NACKed."""
        return self.acked != self.nacked


class FailingStorage(MemoryIdempotencyStorage):
    """Memory storage with a switchable failure mode for one operation."""

    def __init__(
        self,
        *,
        fail_complete: bool = False,
        fail_claim: bool = False,
        fail_release: bool = False,
    ):
        super().__init__()
        self.fail_complete = fail_complete
        self.fail_claim = fail_claim
        self.fail_release = fail_release

    async def complete(self, key: str, *, owner: str) -> None:
        if self.fail_complete:
            raise RuntimeError("complete down")
        await super().complete(key, owner=owner)

    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> ClaimResult:
        if self.fail_claim:
            raise RuntimeError("claim down")
        return await super().claim(key, owner=owner, lease_seconds=lease_seconds)

    async def release(self, key: str, *, owner: str) -> None:
        if self.fail_release:
            raise RuntimeError("release down")
        await super().release(key, owner=owner)


class ExplodingRenewStorage(MemoryIdempotencyStorage):
    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        raise RuntimeError("renew down")


class RefusingRenewStorage(MemoryIdempotencyStorage):
    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        return False


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
    observability_hooks: object | None = None,
) -> PubSubPullRunner:
    return PubSubPullRunner(
        dispatcher,
        subscription,
        bot=bot,
        idempotency_storage=storage,
        renew_interval=renew_interval,
        observability_hooks=observability_hooks,
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


async def test_card_return_forms_have_identical_pubsub_update_behavior() -> None:
    router = Router()

    def card() -> Card:
        return Card(
            header=CardHeader(title="updated"),
            sections=[Section(widgets=[TextParagraph("x")])],
        )

    @router.action("card.direct")
    async def direct(event: ActionEvent) -> Card:
        del event
        return card()

    @router.action("card.variable")
    async def variable(event: ActionEvent) -> Card:
        del event
        result = card()
        return result

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    for action in ("card.direct", "card.variable"):
        payload = json.loads(_action_payload())
        payload["common"]["invokedFunction"] = action
        await runner._handle(FakePubSubMessage(json.dumps(payload), message_id=action))

    updates = [args for kind, args in bot.calls if kind == "update_message"]
    assert [item["name"] for item in updates] == [
        "spaces/A/messages/M1",
        "spaces/A/messages/M1",
    ]


async def test_unmatched_action_emits_safe_warning_diagnostic(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router(name="start"))
    caplog.set_level(logging.DEBUG, logger="chattice.routing")

    await dispatcher.feed_update(ActionEvent(name="start_user_manag"))

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event received: event_type=action action=start_user_manag" in message
        for message in messages
    )
    assert any(
        "unhandled interaction: event_type=action action=start_user_manag" in message
        for message in messages
    )


async def test_matched_handler_debug_diagnostic_includes_identity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router(name="start")

    @router.action("start_user_manage")
    async def open_user_manage(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.DEBUG, logger="chattice.routing")

    result = await dispatcher.feed_update(ActionEvent(name="start_user_manage"))

    assert isinstance(result, Card)
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "handler_selected: router=start observer=action "
        "handler=tests.transports.test_pubsub_runner." in message
        for message in messages
    )
    assert any(
        "handler_completed:" in message and "result_type=Card" in message
        for message in messages
    )


async def test_handler_failure_logs_class_traceback_and_not_raw_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload_secret = "PAYLOAD-SECRET-DO-NOT-LOG"
    router = Router()

    @router.message()
    async def broken(message: MessageEvent) -> str:
        del message
        raise RuntimeError("handler failure")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)
    caplog.set_level(logging.DEBUG, logger="chattice.pubsub")
    logging.getLogger("chattice.pubsub").setLevel(logging.DEBUG)

    await runner._handle(
        FakePubSubMessage(_message_payload(payload_secret), delivery_attempt=1)
    )

    record = next(
        record
        for record in caplog.records
        if record.name == "chattice.pubsub"
        and "delivery failed, nacked" in record.getMessage()
    )
    # Production-safe: exception CLASS in the message, never the text.
    assert "handler failure" not in record.getMessage()
    assert "exception_type=RuntimeError" in record.getMessage()
    assert "message_id=m-1" in record.getMessage()
    assert "attempt=1" in record.getMessage()
    assert "event_type=message" in record.getMessage()
    # Debug mode: traceback (containing the message) is attached.
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError
    assert payload_secret not in "\n".join(
        captured.getMessage() for captured in caplog.records
    )


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
    """A completion failure must not leave the delivery ACKed."""
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
    assert storage.renew_calls >= 2  # the lease is being renewed
    release.set()
    await task


async def test_same_message_id_in_two_subscriptions_both_processed() -> None:
    """The dedupe key includes the subscription."""
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
    """An old attempt cannot release a new owner's claim after takeover."""
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


# --------------------------------------------------------------------------
# Helpers and unit-level branches
# --------------------------------------------------------------------------


def test_event_context_handles_unknown_event() -> None:
    assert _event_context(None) == "event_type=unknown"


def test_runner_rejects_nonpositive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        PubSubPullRunner(Dispatcher(), "projects/P/subscriptions/S", max_concurrency=0)


def test_import_pubsub_requires_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "google.cloud", None)
    with pytest.raises(ChatticeError, match="pubsub extra"):
        _import_pubsub()


async def test_keyed_lock_registry_drops_cancelled_waiter() -> None:
    registry = _KeyedLockRegistry()
    await registry.acquire("k")  # hold the lock
    waiter = asyncio.create_task(registry.acquire("k"))
    await asyncio.sleep(0)  # let the waiter queue up
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    registry.release("k")
    # The registry must stay usable: no dead lock left behind.
    await asyncio.wait_for(registry.acquire("k"), timeout=1.0)


class _BrokenHook:
    async def delivery_acked(self, *args: object) -> None:
        raise RuntimeError("hook down")


class _SilentHook:
    """Observability hook providing none of the optional methods."""


async def test_observability_hook_failure_never_breaks_delivery() -> None:
    router = Router()

    @router.message(_always)
    async def ping(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, MockBot(), observability_hooks=_BrokenHook())

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.acked and not message.nacked


async def test_missing_hook_method_is_ignored() -> None:
    router = Router()

    @router.message(_always)
    async def ping(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, MockBot(), observability_hooks=_SilentHook())

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.acked


# --------------------------------------------------------------------------
# run()/close() lifecycle over a fake subscriber client
# --------------------------------------------------------------------------


class FakePullFuture:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def result(self) -> None:
        if self._error is not None:
            raise self._error
        return None


class FakeSubscriberClient:
    def __init__(self, pull_future: FakePullFuture) -> None:
        self.pull_future = pull_future
        self.closed = False
        self.subscription: str | None = None
        self.callback: Any = None

    def subscribe(
        self, subscription: str, *, callback: Any, flow_control: Any
    ) -> FakePullFuture:
        self.subscription = subscription
        self.callback = callback
        return self.pull_future

    def close(self) -> None:
        self.closed = True


def _patch_pubsub(
    monkeypatch: pytest.MonkeyPatch, pull_future: FakePullFuture
) -> FakeSubscriberClient:
    client = FakeSubscriberClient(pull_future)

    class FakePubsubV1:
        class types:
            class FlowControl:
                def __init__(self, **kwargs: Any) -> None:
                    self.kwargs = kwargs

        @staticmethod
        def SubscriberClient(credentials: Any = None) -> FakeSubscriberClient:
            del credentials
            return client

    module = ModuleType("google.cloud")
    cast(Any, module).pubsub_v1 = FakePubsubV1
    monkeypatch.setitem(sys.modules, "google.cloud", module)
    return client


async def test_run_returns_after_stop_event_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pull_future = FakePullFuture()
    client = _patch_pubsub(monkeypatch, pull_future)
    runner = _runner(Dispatcher())

    stop = asyncio.Event()
    stop.set()
    await runner.run(stop)

    assert client.subscription == "projects/P/subscriptions/S"
    assert client.closed
    assert pull_future.cancelled
    assert runner._closed and runner._subscriber is None


async def test_run_surfaces_subscriber_error_as_chattice_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pull_future = FakePullFuture(error=RuntimeError("stream dead"))
    _patch_pubsub(monkeypatch, pull_future)
    runner = _runner(Dispatcher())

    stop = asyncio.Event()  # NOT set: the stream ends on its own
    with pytest.raises(ChatticeError, match="subscriber failed"):
        await runner.run(stop)

    assert pull_future.cancelled and runner._closed


async def test_run_surfaces_clean_stream_end_as_chattice_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pull_future = FakePullFuture()  # ends without an exception
    _patch_pubsub(monkeypatch, pull_future)
    runner = _runner(Dispatcher())

    stop = asyncio.Event()  # NOT set
    with pytest.raises(ChatticeError, match="stopped unexpectedly"):
        await runner.run(stop)

    assert pull_future.cancelled and runner._closed


class _SignalLoop:
    """Loop double recording add_signal_handler calls."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        self._failure = failure
        self.added: list[int] = []

    def add_signal_handler(self, sig: Any, callback: Any) -> None:
        if self._failure is not None:
            raise self._failure
        self.added.append(sig)


@pytest.mark.parametrize("failure", [None, NotImplementedError(), RuntimeError()])
def test_install_signals_tolerates_platform_limits(
    failure: Exception | None,
) -> None:
    runner = _runner(Dispatcher())
    loop = _SignalLoop(failure=failure)
    runner._loop = cast(asyncio.AbstractEventLoop, loop)

    stop = runner._install_signals()

    assert isinstance(stop, asyncio.Event)
    if failure is None:
        assert len(loop.added) == 2  # SIGINT + SIGTERM
    else:
        assert loop.added == []


async def test_resolve_credentials_prefers_direct_credentials() -> None:
    credentials = cast(Any, SimpleNamespace())
    runner = PubSubPullRunner(
        Dispatcher(), "projects/P/subscriptions/S", credentials=credentials
    )
    assert await runner._resolve_credentials() is credentials


async def test_resolve_credentials_calls_provider_off_loop() -> None:
    calls: list[int] = []

    def provider() -> Any:
        calls.append(1)
        return SimpleNamespace()

    runner = PubSubPullRunner(
        Dispatcher(),
        "projects/P/subscriptions/S",
        credentials_provider=cast(CredentialsProvider, provider),
    )
    resolved = await runner._resolve_credentials()
    assert calls == [1]
    assert resolved is not None


async def test_close_closes_subscriber_and_drains_scheduled() -> None:
    runner = _runner(Dispatcher())
    subscriber = SimpleNamespace(close=lambda: None)
    runner._subscriber = subscriber
    done: concurrent.futures.Future[None] = concurrent.futures.Future()
    done.set_result(None)
    runner._scheduled.add(done)

    await runner.close()

    assert runner._subscriber is None
    assert not runner._scheduled


async def test_schedule_skips_after_close() -> None:
    runner = _runner(Dispatcher())
    await runner.close()  # _loop reset to None

    runner._schedule(FakePubSubMessage(_message_payload()))

    assert not runner._scheduled


async def test_schedule_swallows_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner(Dispatcher())
    runner._loop = asyncio.get_running_loop()

    def boom(coro: Any, loop: Any) -> Any:
        coro.close()
        raise RuntimeError("loop gone")

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", boom)
    runner._schedule(FakePubSubMessage(_message_payload()))

    assert not runner._scheduled


# --------------------------------------------------------------------------
# Renewal loop terminal paths
# --------------------------------------------------------------------------


async def test_renew_loop_stops_after_storage_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    runner = _runner(dispatcher, storage=ExplodingRenewStorage(), renew_interval=0.01)
    message = FakePubSubMessage(_message_payload())

    with caplog.at_level(logging.ERROR, logger="chattice.pubsub"):
        await runner._renew_loop("k", "owner", message)

    assert any("renewal failed" in record.getMessage() for record in caplog.records)


async def test_renew_loop_stops_when_lease_is_lost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    runner = _runner(dispatcher, storage=RefusingRenewStorage(), renew_interval=0.01)
    message = FakePubSubMessage(_message_payload())

    with caplog.at_level(logging.ERROR, logger="chattice.pubsub"):
        await runner._renew_loop("k", "owner", message)

    assert any("renewal refused" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------
# Failure notifications and release
# --------------------------------------------------------------------------


class NoSendBot(MockBot):
    async def send_message(self, space: Any, text: Any = None, **kwargs: Any) -> Any:
        raise RuntimeError("api down")


async def test_poison_notification_failure_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = _runner(Dispatcher(), NoSendBot())

    with caplog.at_level(logging.ERROR, logger="chattice.pubsub"):
        await runner._notify_poison(EventFactory.message("x"), "RuntimeError")

    assert any(
        "poison notification failed" in record.getMessage() for record in caplog.records
    )


async def test_release_failure_still_nacks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message(_always)
    async def broken(message: MessageEvent) -> str:
        raise RuntimeError("boom")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(
        dispatcher, storage=FailingStorage(fail_release=True), renew_interval=None
    )

    message = FakePubSubMessage(_message_payload(), delivery_attempt=1)
    with caplog.at_level(logging.ERROR, logger="chattice.pubsub"):
        await runner._handle(message)

    assert message.nacked and not message.acked
    assert any("release failed" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------
# Parsing branches
# --------------------------------------------------------------------------


def test_parse_accepts_bytes_payload() -> None:
    runner = _runner(Dispatcher())
    event = runner._parse(FakePubSubMessage(_message_payload().encode()))
    assert isinstance(event, MessageEvent)


def test_parse_rejects_non_text_data() -> None:
    runner = _runner(Dispatcher())
    with pytest.raises(PubSubEnvelopeError, match="not text"):
        runner._parse(FakePubSubMessage(12345))


def test_parse_rejects_invalid_json() -> None:
    runner = _runner(Dispatcher())
    with pytest.raises(PubSubEnvelopeError, match="not valid JSON"):
        runner._parse(FakePubSubMessage("{nope"))


def test_parse_rejects_non_object_payload() -> None:
    runner = _runner(Dispatcher())
    with pytest.raises(PubSubEnvelopeError, match="JSON object"):
        runner._parse(FakePubSubMessage("[1,2,3]"))


# --------------------------------------------------------------------------
# Answer routing edge cases
# --------------------------------------------------------------------------


async def test_dialog_answer_without_bot_acks() -> None:
    router = Router()

    @router.action("card.clicked")
    async def dialog(event: ActionEvent) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)  # no Bot: the explanation send is skipped

    message = FakePubSubMessage(_action_payload())
    await runner._handle(message)

    assert message.acked and not message.nacked


async def test_answer_dropped_without_bot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message(_always)
    async def pong(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)  # no Bot configured

    message = FakePubSubMessage(_message_payload())
    with caplog.at_level(logging.WARNING, logger="chattice.pubsub"):
        await runner._handle(message)

    assert message.acked
    assert any("no Bot configured" in record.getMessage() for record in caplog.records)


async def test_answer_dropped_without_space(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message(_always)
    async def pong(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    payload = json.loads(_message_payload())
    del payload["space"]  # the parsed event carries no space
    message = FakePubSubMessage(json.dumps(payload))
    with caplog.at_level(logging.WARNING, logger="chattice.pubsub"):
        await runner._handle(message)

    assert message.acked
    assert any("no space" in record.getMessage() for record in caplog.records)
    assert not bot.calls


async def test_unsupported_answer_type_warns_and_acks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message(_always)
    async def odd(message: MessageEvent) -> Any:
        return {"unexpected": True}

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    message = FakePubSubMessage(_message_payload())
    with caplog.at_level(logging.WARNING, logger="chattice.pubsub"):
        await runner._handle(message)

    assert message.acked
    assert not bot.calls
    assert any("type unsupported" in record.getMessage() for record in caplog.records)


async def test_card_answer_from_message_event_sends_fresh() -> None:
    router = Router()

    @router.message(_always)
    async def give_card(message: MessageEvent) -> Card:
        return Card(
            header=CardHeader(title="fresh"),
            sections=[Section(widgets=[TextParagraph("x")])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()
    runner = _runner(dispatcher, bot)

    message = FakePubSubMessage(_message_payload())
    await runner._handle(message)

    assert message.acked
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert len(sent) == 1
    assert sent[0]["space"] == "spaces/A"
    assert sent[0]["card"]["header"]["title"] == "fresh"


async def test_delivery_without_attempt_and_without_space_is_processed() -> None:
    router = Router()

    @router.message(_always)
    async def silent(message: MessageEvent) -> None:
        return None

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher)

    payload = json.loads(_message_payload())
    del payload["space"]
    message = FakePubSubMessage(json.dumps(payload), delivery_attempt=None)
    await runner._handle(message)

    assert message.acked and not message.nacked


# --------------------------------------------------------------------------
# Claim, scheduling, and delivery-diagnostics branches
# --------------------------------------------------------------------------


def test_event_context_includes_command_id() -> None:
    context = _event_context(CommandEvent(command_id=7))
    assert "command_id=7" in context
    assert "event_type=command" in context


def test_delivery_log_includes_command_id() -> None:
    runner = _runner(Dispatcher())
    # No assertion: the structured INFO line must include the command
    # identity without raising for a command event.
    runner._log_delivery_received(
        FakePubSubMessage(_message_payload()), CommandEvent(command_id=7)
    )


async def test_active_claim_by_another_owner_nacks() -> None:
    storage = MemoryIdempotencyStorage()
    dispatcher = Dispatcher()
    runner = _runner(dispatcher, storage=storage)

    key = "projects/P/subscriptions/S:m-active"
    await storage.claim(key, owner="other-owner", lease_seconds=300.0)

    message = FakePubSubMessage(_message_payload(), message_id="m-active")
    await runner._handle(message)

    assert message.nacked and not message.acked
    assert message.exactly_one_terminal


async def test_schedule_processes_delivery_on_running_loop() -> None:
    router = Router()

    @router.message(_always)
    async def pong(message: MessageEvent) -> str:
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, MockBot())
    runner._loop = asyncio.get_running_loop()

    message = FakePubSubMessage(_message_payload())
    runner._schedule(message)
    await asyncio.sleep(0.1)

    assert message.acked and not message.nacked
    assert not runner._scheduled  # the done-callback discarded the future


def test_track_stale_interaction_warns_but_does_not_advance(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = _runner(Dispatcher())
    now = datetime.now(UTC)
    card = "spaces/A/messages/M1"
    newer = ActionEvent(name="a", message=MessageRef(name=card), event_time=now)
    older = ActionEvent(
        name="a", message=MessageRef(name=card), event_time=now - timedelta(seconds=2)
    )

    with caplog.at_level(logging.WARNING, logger="chattice.pubsub"):
        runner._track_stale_interaction(newer)  # baseline, no warning
        runner._track_stale_interaction(older)  # stale → warning

    assert any(
        "stale interaction detected" in record.getMessage() for record in caplog.records
    )
    # The baseline was NOT advanced by the stale event.
    assert runner._latest_event_times[card] == now


def test_delayed_interaction_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = _runner(Dispatcher())  # default delayed_event_ms=5000
    late = EventFactory.message(
        "x", event_time=datetime.now(UTC) - timedelta(seconds=6)
    )

    with caplog.at_level(logging.WARNING, logger="chattice.pubsub"):
        runner._log_delivery_received(FakePubSubMessage(_message_payload()), late)

    assert any(
        "delayed interaction received" in record.getMessage()
        for record in caplog.records
    )


# --------------------------------------------------------------------------
# Outbound failure branches
# --------------------------------------------------------------------------


class ExplodingUpdateBot(MockBot):
    async def update_message(self, name: Any, text: Any = None, **kwargs: Any) -> Any:
        raise RuntimeError("update down")


async def test_card_update_failure_nacks() -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(event: ActionEvent) -> Card:
        return Card(
            header=CardHeader(title="updated"),
            sections=[Section(widgets=[TextParagraph("x")])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, ExplodingUpdateBot())

    message = FakePubSubMessage(_action_payload(), delivery_attempt=1)
    await runner._handle(message)

    assert message.nacked and not message.acked


async def test_card_send_failure_nacks() -> None:
    router = Router()

    @router.message(_always)
    async def give_card(message: MessageEvent) -> Card:
        return Card(
            header=CardHeader(title="fresh"),
            sections=[Section(widgets=[TextParagraph("x")])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = _runner(dispatcher, NoSendBot())

    message = FakePubSubMessage(_message_payload(), delivery_attempt=1)
    await runner._handle(message)

    assert message.nacked and not message.acked


class RenewExplodingRunner(PubSubPullRunner):
    async def _renew_loop(self, key: str, owner: str, message: Any) -> None:
        raise RuntimeError("renew explode")


async def test_renewal_task_failure_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    router = Router()

    @router.message(_always)
    async def slow(message: MessageEvent) -> str:
        started.set()
        await release.wait()
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = RenewExplodingRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        bot=MockBot(),
        idempotency_storage=MemoryIdempotencyStorage(),
        renew_interval=0.01,
    )

    message = FakePubSubMessage(_message_payload())
    task = asyncio.create_task(runner._handle(message))
    await started.wait()  # the renewal task has been spawned...
    await asyncio.sleep(0.05)  # ...and had time to fail with RuntimeError
    release.set()
    with caplog.at_level(logging.ERROR, logger="chattice.pubsub"):
        await task

    assert message.acked and not message.nacked  # delivery unaffected
    assert any(
        "renewal task failed" in record.getMessage() for record in caplog.records
    )
