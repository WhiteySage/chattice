"""Observability hooks around dispatch."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import MessageEvent


def _event() -> MessageEvent:
    event = parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2026-08-15T10:00:00Z",
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
