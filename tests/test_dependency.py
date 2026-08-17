"""Signature-based dependency injection tests."""

import pytest

from chattice import Dispatcher, Router
from chattice.dispatcher.dependency import HandlerCallback, build_handler_plan
from chattice.events import Event, MessageEvent
from chattice.exceptions import DependencyResolutionError, InvalidHandlerError


async def test_event_annotation_and_context_name_injection() -> None:
    database = object()
    config = object()
    router = Router()

    @router.message()
    async def handler(
        arbitrary_name: MessageEvent, database: object, config: object
    ) -> tuple[MessageEvent, object, object]:
        return arbitrary_name, database, config

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    event = MessageEvent(text="hello")

    assert await dispatcher.feed_update(event, database=database, config=config) == (
        event,
        database,
        config,
    )


async def test_unannotated_event_alias_is_injected() -> None:
    router = Router()

    @router.event()
    async def handler(event: object) -> object:
        return event

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    event = Event()

    # An explicit non-Event annotation is not an event-injection request.
    with pytest.raises(DependencyResolutionError, match="event"):
        await dispatcher.feed_update(event)

    second = Dispatcher()

    @second.event()
    async def untyped(event):  # type: ignore[no-untyped-def]
        return event

    assert await second.feed_update(event) is event


async def test_default_parameter_is_used_when_context_is_absent() -> None:
    router = Router()

    @router.message()
    async def handler(message: MessageEvent, label: str = "default") -> str:
        del message
        return label

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent()) == "default"
    assert await dispatcher.feed_update(MessageEvent(), label="provided") == "provided"


async def test_missing_required_dependency_has_clear_error() -> None:
    router = Router()

    @router.message()
    async def handler(message: MessageEvent, database: object) -> object:
        del message
        return database

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    with pytest.raises(DependencyResolutionError, match="database"):
        await dispatcher.feed_update(MessageEvent())


def test_handler_signature_plan_is_cached() -> None:
    build_handler_plan.cache_clear()

    async def handler(event: Event) -> None:
        del event

    first = build_handler_plan(handler)
    second = build_handler_plan(handler)

    assert first is second
    assert build_handler_plan.cache_info().hits == 1


@pytest.mark.parametrize("kind", ["args", "kwargs", "positional"])
def test_invalid_signature_is_rejected_at_registration(kind: str) -> None:
    router = Router()

    async def args(*values: object) -> None:
        del values

    async def kwargs(**values: object) -> None:
        del values

    async def positional(value: object, /) -> None:
        del value

    callbacks: dict[str, HandlerCallback] = {
        "args": args,
        "kwargs": kwargs,
        "positional": positional,
    }

    with pytest.raises(InvalidHandlerError, match="unsupported kind"):
        router.event.register(callbacks[kind])


async def test_non_async_handler_fails_clearly() -> None:
    router = Router()

    def handler(event: Event) -> str:
        del event
        return "sync"

    router.event.register(handler)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    with pytest.raises(InvalidHandlerError, match="must be async"):
        await dispatcher.feed_update(Event())
