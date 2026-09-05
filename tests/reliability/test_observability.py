"""Observability hooks around dispatch."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import MessageEvent


def _event() -> MessageEvent:
    event = parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2000-01-01T10:00:00Z",
            "message": {"text": "ping"},
            "user": {"name": "users/1"},
            "space": {"name": "spaces/AAA"},
        }
    )
    assert isinstance(event, MessageEvent)
    return event


class _RecordingHooks:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error: BaseException | None = None

    async def before_event(self, event: object, data: object) -> None:
        self.calls.append(("before", type(event).__name__))

    async def after_event(
        self, event: object, data: object, result: object, error: BaseException | None
    ) -> None:
        self.calls.append(("after", type(event).__name__))
        self.error = error


async def test_hooks_called_in_order() -> None:
    hooks = _RecordingHooks()
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher(observability_hooks=hooks)
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(_event())
    assert result == "ok"
    assert hooks.calls == [("before", "MessageEvent"), ("after", "MessageEvent")]
    assert hooks.error is None


class _RaisingHooks:
    def __init__(self) -> None:
        self.after_calls = 0

    async def before_event(self, event: object, data: object) -> None:
        raise RuntimeError("hook failure")

    async def after_event(
        self, event: object, data: object, result: object, error: BaseException | None
    ) -> None:
        self.after_calls += 1


async def test_raising_hook_does_not_break_dispatch() -> None:
    hooks = _RaisingHooks()
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher(observability_hooks=hooks)
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(_event())
    assert result == "ok"  # hook failure logged, dispatch unaffected


class _FullHooks:
    """Implements the complete optional hook surface."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def before_event(self, event: object, data: object) -> None:
        self.calls.append("before_event")

    async def after_event(
        self, event: object, data: object, result: object, error: BaseException | None
    ) -> None:
        self.calls.append("after_event")

    async def before_handler(self, event: object, data: object, handler: str) -> None:
        self.calls.append(f"before_handler:{handler.split('.')[-1]}")

    async def after_handler(
        self, event: object, data: object, handler: str, result: object
    ) -> None:
        self.calls.append(f"after_handler:{handler.split('.')[-1]}")


async def test_handler_hooks_receive_handler_name() -> None:
    hooks = _FullHooks()
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher(observability_hooks=hooks)
    dispatcher.include_router(router)
    await dispatcher.feed_update(_event())

    assert "before_handler:handler" in hooks.calls
    assert "after_handler:handler" in hooks.calls
    # handler hooks fire between the event hooks
    assert hooks.calls.index("before_event") < hooks.calls.index(
        "before_handler:handler"
    )
    assert hooks.calls.index("after_handler:handler") < hooks.calls.index("after_event")


async def test_legacy_two_hook_implementations_still_work() -> None:
    """Classes implementing only before/after_event stay compatible."""
    hooks = _RecordingHooks()
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher(observability_hooks=hooks)
    dispatcher.include_router(router)
    await dispatcher.feed_update(_event())
    assert hooks.calls == [("before", "MessageEvent"), ("after", "MessageEvent")]


async def test_outbound_and_delivery_hooks_fire() -> None:
    import json

    from chattice.testing import MockBot
    from chattice.transports.pubsub_runner import PubSubPullRunner
    from tests.transports.test_pubsub_runner import FakePubSubMessage

    class _DeliveryHooks:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def before_event(self, event: object, data: object) -> None:
            pass

        async def after_event(
            self,
            event: object,
            data: object,
            result: object,
            error: BaseException | None,
        ) -> None:
            pass

        async def before_outbound(self, event: object, operation: str) -> None:
            self.calls.append(f"before_outbound:{operation}")

        async def after_outbound(self, event: object, operation: str) -> None:
            self.calls.append(f"after_outbound:{operation}")

        async def delivery_acked(self, message_id: str, event: object) -> None:
            self.calls.append(f"acked:{message_id}")

        async def delivery_nacked(self, message_id: str, event: object) -> None:
            self.calls.append(f"nacked:{message_id}")

    hooks = _DeliveryHooks()
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        return "ok"

    dispatcher = Dispatcher(observability_hooks=hooks)
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        bot=MockBot(),
        observability_hooks=hooks,
    )
    message = FakePubSubMessage(
        json.dumps(
            {
                "type": "MESSAGE",
                "message": {"text": "ping"},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        ),
        message_id="m-hooks",
    )
    await runner._handle(message)

    assert "before_outbound:send_message" in hooks.calls
    assert "after_outbound:send_message" in hooks.calls
    assert "acked:m-hooks" in hooks.calls
    assert not any(call.startswith("nacked:") for call in hooks.calls)
