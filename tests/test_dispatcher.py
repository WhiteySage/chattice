"""End-to-end dispatcher and error-observer tests."""

import pytest

from chattice import Dispatcher, F, Router
from chattice.events import ActionEvent, ErrorEvent, Event, MessageEvent, UnknownEvent
from chattice.exceptions import StopPropagation


async def test_basic_message_routing_and_return_identity() -> None:
    result = object()
    router = Router()

    @router.message()
    async def echo(message: MessageEvent) -> object:
        assert message.text == "hello"
        return result

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="hello")) is result


async def test_action_name_shortcut() -> None:
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> str:
        return action.name

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(ActionEvent(name="other")) is None
    assert (
        await dispatcher.feed_update(ActionEvent(name="deploy.confirm"))
        == "deploy.confirm"
    )


async def test_specific_observers_have_global_precedence_over_generic_fallback() -> (
    None
):
    generic_parent = Router(name="generic")
    specific_child = Router(name="specific")

    @generic_parent.event()
    async def generic(event: Event) -> str:
        del event
        return "generic"

    @specific_child.message()
    async def specific(message: MessageEvent) -> str:
        del message
        return "specific"

    generic_parent.include_router(specific_child)
    dispatcher = Dispatcher()
    dispatcher.include_router(generic_parent)

    assert await dispatcher.feed_update(MessageEvent()) == "specific"
    assert await dispatcher.feed_update(Event()) == "generic"


async def test_generic_observer_is_used_when_specific_observer_has_no_match() -> None:
    router = Router()

    @router.message(F.text == "specific")
    async def specific(message: MessageEvent) -> str:
        del message
        return "specific"

    @router.event()
    async def generic(event: Event) -> str:
        del event
        return "generic"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(MessageEvent(text="other")) == "generic"


async def test_unknown_observer_preserves_future_type() -> None:
    router = Router()

    @router.unknown_event()
    async def unknown(event: UnknownEvent) -> str:
        return event.original_type

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert (
        await dispatcher.feed_update(UnknownEvent(original_type="FUTURE")) == "FUTURE"
    )


async def test_unknown_event_can_fall_back_to_generic_observer() -> None:
    dispatcher = Dispatcher()

    @dispatcher.event()
    async def generic(event: Event) -> str:
        return event.event_type

    assert (
        await dispatcher.feed_update(UnknownEvent(original_type="FUTURE")) == "unknown"
    )


async def test_feed_update_rejects_non_domain_values() -> None:
    dispatcher = Dispatcher()

    with pytest.raises(TypeError, match="Event instances"):
        await dispatcher.feed_update({"type": "MESSAGE"})  # type: ignore[arg-type]


async def test_error_observer_handles_exception() -> None:
    expected = ValueError("boom")
    router = Router()

    @router.message()
    async def failing(message: MessageEvent) -> None:
        del message
        raise expected

    @router.error()
    async def handle(error: ErrorEvent) -> tuple[Event, Exception]:
        return error.source_event, error.exception

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    source = MessageEvent(text="hello")

    assert await dispatcher.feed_update(source) == (source, expected)


async def test_unhandled_exception_preserves_original_object() -> None:
    expected = ValueError("boom")
    dispatcher = Dispatcher()

    @dispatcher.message()
    async def failing(message: MessageEvent) -> None:
        del message
        raise expected

    with pytest.raises(ValueError) as caught:
        await dispatcher.feed_update(MessageEvent())
    assert caught.value is expected


async def test_error_handler_failure_is_chained_to_original() -> None:
    dispatcher = Dispatcher()

    @dispatcher.message()
    async def failing(message: MessageEvent) -> None:
        del message
        raise ValueError("original")

    @dispatcher.error()
    async def broken(error: ErrorEvent) -> None:
        del error
        raise RuntimeError("error handler failed")

    with pytest.raises(RuntimeError, match="error handler failed") as caught:
        await dispatcher.feed_update(MessageEvent())
    assert isinstance(caught.value.__cause__, ValueError)


async def test_stop_in_error_observer_does_not_silence_original_exception() -> None:
    dispatcher = Dispatcher()

    @dispatcher.message()
    async def failing(message: MessageEvent) -> None:
        del message
        raise ValueError("original")

    @dispatcher.error()
    async def stop(error: ErrorEvent) -> None:
        del error
        raise StopPropagation

    with pytest.raises(ValueError, match="original"):
        await dispatcher.feed_update(MessageEvent())


def test_public_api_exports_are_intentional() -> None:
    import chattice

    assert chattice.__all__ == ["Dispatcher", "F", "Router", "__version__"]
    assert chattice.__version__ == "0.14.0b3"
