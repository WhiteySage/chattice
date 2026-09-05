"""Router hierarchy, registration, and propagation tests."""

from collections.abc import Mapping

import pytest

from chattice import Dispatcher, F, Router
from chattice.events import Event, MessageEvent
from chattice.exceptions import (
    RouterConfigurationError,
    SkipHandler,
    StopPropagation,
)


async def test_decorator_and_programmatic_registration() -> None:
    router = Router(name="feature")

    async def programmatic(message: MessageEvent) -> str:
        return message.text

    returned = router.message.register(programmatic, F.text == "hello")

    assert returned is programmatic
    assert len(router.message.handlers) == 1

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    assert await dispatcher.feed_update(MessageEvent(text="hello")) == "hello"


async def test_depth_first_router_traversal_preserves_inclusion_order() -> None:
    first = Router(name="first")
    grandchild = Router(name="grandchild")
    second = Router(name="second")

    @first.message(F.text == "no")
    async def first_handler(message: MessageEvent) -> None:
        del message

    @grandchild.message()
    async def grandchild_handler(message: MessageEvent) -> str:
        del message
        return "grandchild"

    @second.message()
    async def second_handler(message: MessageEvent) -> str:
        del message
        return "second"

    first.include_router(grandchild)
    dispatcher = Dispatcher()
    dispatcher.include_router(first)
    dispatcher.include_router(second)

    assert await dispatcher.feed_update(MessageEvent()) == "grandchild"


def test_router_rejects_self_inclusion() -> None:
    router = Router(name="self")

    with pytest.raises(RouterConfigurationError, match="itself"):
        router.include_router(router)


def test_router_rejects_cycles() -> None:
    parent = Router(name="parent")
    child = Router(name="child")
    parent.include_router(child)

    with pytest.raises(RouterConfigurationError, match="cycle"):
        child.include_router(parent)


def test_router_rejects_ambiguous_parent_ownership() -> None:
    first_parent = Router(name="first")
    second_parent = Router(name="second")
    child = Router(name="child")
    first_parent.include_router(child)

    with pytest.raises(RouterConfigurationError, match="already attached"):
        second_parent.include_router(child)


def test_router_debug_properties_and_repr() -> None:
    parent = Router(name="parent")
    child = Router(name="child")
    assert parent.include_router(child) is child

    assert child.parent is parent
    assert parent.children == (child,)
    assert "parent" in repr(parent)
    assert "child" in repr(child)


async def test_first_matching_handler_wins() -> None:
    router = Router()
    calls: list[str] = []

    @router.message(F.text == "ping")
    async def first(message: MessageEvent) -> str:
        del message
        calls.append("first")
        return "one"

    @router.message(F.text == "ping")
    async def second(message: MessageEvent) -> str:
        del message
        calls.append("second")
        return "two"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="ping")) == "one"
    assert calls == ["first"]


async def test_skip_handler_continues_with_next_candidate() -> None:
    router = Router()

    @router.message()
    async def skipped(message: MessageEvent) -> None:
        del message
        raise SkipHandler

    @router.message()
    async def fallback(message: MessageEvent) -> str:
        del message
        return "fallback"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) == "fallback"


async def test_filter_can_explicitly_skip_candidate() -> None:
    router = Router()

    async def skip_filter(event: Event, context: Mapping[str, object]) -> bool:
        del event, context
        raise SkipHandler

    @router.message(skip_filter)
    async def skipped(message: MessageEvent) -> None:
        del message

    @router.message()
    async def fallback(message: MessageEvent) -> str:
        del message
        return "fallback"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) == "fallback"


async def test_stop_propagation_prevents_later_and_generic_handlers() -> None:
    router = Router()
    calls: list[str] = []

    @router.message()
    async def stop(message: MessageEvent) -> None:
        del message
        calls.append("stop")
        raise StopPropagation

    @router.message()
    async def later(message: MessageEvent) -> None:
        del message
        calls.append("later")

    @router.event()
    async def generic(event: Event) -> None:
        del event
        calls.append("generic")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) is None
    assert calls == ["stop"]


async def test_no_match_returns_none() -> None:
    router = Router()

    @router.message(F.text == "ping")
    async def ping(message: MessageEvent) -> str:
        del message
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="other")) is None
