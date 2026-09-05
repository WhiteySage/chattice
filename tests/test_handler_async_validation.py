"""Async handler contract: rejection before the first event."""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable

import pytest

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.exceptions import InvalidHandlerError
from chattice.workspace_events import EventsRouter


def _wrapping_decorator(
    fn: Callable[..., Awaitable[object]],
) -> Callable[..., Awaitable[object]]:
    @functools.wraps(fn)
    async def wrapper(*args: object, **kwargs: object) -> object:
        return await fn(*args, **kwargs)

    return wrapper


class _AsyncCallable:
    async def __call__(self) -> str:
        return "called"


class _SyncCallable:
    def __call__(self) -> None:
        raise AssertionError("sync callable body must not execute")


def test_sync_def_rejected_at_registration() -> None:
    router = Router()

    with pytest.raises(InvalidHandlerError, match="must be asynchronous"):

        @router.message()
        def handler() -> None:
            raise AssertionError("sync handler body must not execute")


def test_sync_handler_body_never_executes() -> None:
    """Critical regression: sync handler must be rejected before any call."""
    router = Router()
    called = False

    def bad_handler() -> None:
        nonlocal called
        called = True

    with pytest.raises(InvalidHandlerError, match="must be asynchronous"):
        router.event.register(bad_handler)

    assert called is False


def test_sync_callable_object_rejected() -> None:
    router = Router()

    with pytest.raises(InvalidHandlerError, match="must be asynchronous"):
        router.message()(_SyncCallable())


async def test_decorated_async_accepted() -> None:
    router = Router()

    @router.message()
    @_wrapping_decorator
    async def handler(message: MessageEvent) -> str:
        return f"echo:{message.text}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    assert await dispatcher.feed_update(MessageEvent(text="hi")) == "echo:hi"


async def test_async_callable_object_accepted() -> None:
    router = Router()
    router.message()(_AsyncCallable())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    assert await dispatcher.feed_update(MessageEvent(text="hi")) == "called"


def test_events_sync_handler_rejected_at_registration() -> None:
    """Workspace Events runtime rejects sync handlers the same way."""
    router = EventsRouter()
    called = False

    def bad_handler() -> None:
        nonlocal called
        called = True

    with pytest.raises(InvalidHandlerError, match="must be asynchronous"):
        router.workspace_event.register(bad_handler)

    assert called is False
