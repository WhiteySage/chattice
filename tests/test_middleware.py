"""Middleware composition and context behavior."""

from collections.abc import MutableMapping

import pytest

from chattice import Dispatcher, F, Router
from chattice.events import Event, MessageEvent
from chattice.middleware import BaseMiddleware, NextHandler


class TraceMiddleware(BaseMiddleware):
    def __init__(self, label: str, trace: list[str]) -> None:
        self.label = label
        self.trace = trace

    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        self.trace.append(f"{self.label} before")
        result = await handler(event, data)
        self.trace.append(f"{self.label} after")
        return result


async def test_middleware_wraps_in_registration_order() -> None:
    trace: list[str] = []
    router = Router()
    router.middleware(TraceMiddleware("A", trace))
    router.middleware(TraceMiddleware("B", trace))

    @router.message()
    async def handler(message: MessageEvent) -> str:
        del message
        trace.append("handler")
        return "result"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) == "result"
    assert trace == ["A before", "B before", "handler", "B after", "A after"]


async def test_parent_middleware_wraps_descendant_middleware() -> None:
    trace: list[str] = []
    parent = Router(name="parent")
    child = Router(name="child")
    parent.middleware(TraceMiddleware("parent", trace))
    child.middleware(TraceMiddleware("child", trace))

    @child.message()
    async def handler(message: MessageEvent) -> None:
        del message
        trace.append("handler")

    parent.include_router(child)
    dispatcher = Dispatcher()
    dispatcher.include_router(parent)
    await dispatcher.feed_update(MessageEvent())

    assert trace == [
        "parent before",
        "child before",
        "handler",
        "child after",
        "parent after",
    ]


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, database: object) -> None:
        self.database = database

    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        data["database"] = self.database
        return await handler(event, data)


async def test_middleware_mutation_supplies_dependency() -> None:
    database = object()
    router = Router()
    router.middleware.register(DatabaseMiddleware(database))

    @router.message()
    async def handler(message: MessageEvent, database: object) -> object:
        del message
        return database

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) is database


class ShortCircuitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        del handler, event, data
        return "short-circuit"


async def test_middleware_can_short_circuit_handler() -> None:
    router = Router()
    router.middleware(ShortCircuitMiddleware())
    called = False

    @router.message()
    async def handler(message: MessageEvent) -> None:
        nonlocal called
        del message
        called = True

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) == "short-circuit"
    assert not called


class TransformErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        try:
            return await handler(event, data)
        except ValueError as error:
            raise RuntimeError("transformed") from error


async def test_middleware_can_transform_exception_with_chaining() -> None:
    router = Router()
    router.middleware(TransformErrorMiddleware())

    @router.message()
    async def handler(message: MessageEvent) -> None:
        del message
        raise ValueError("original")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    with pytest.raises(RuntimeError, match="transformed") as caught:
        await dispatcher.feed_update(MessageEvent())
    assert isinstance(caught.value.__cause__, ValueError)


async def test_middleware_does_not_run_when_filters_do_not_match() -> None:
    trace: list[str] = []
    router = Router()
    router.middleware(TraceMiddleware("middleware", trace))

    @router.message(F.text == "match")
    async def handler(message: MessageEvent) -> None:
        del message

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="other")) is None
    assert trace == []
