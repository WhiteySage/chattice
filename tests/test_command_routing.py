"""Google-native command kinds and explicit preview enrollment."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.capabilities import PreviewCapabilities, PreviewFeature
from chattice.events import CommandEvent, CommandKind, Event


def _message_action() -> Event:
    return parse_interaction(
        {
            "type": "APP_COMMAND",
            "message": {
                "name": "spaces/A/messages/M",
                "text": "remember this",
            },
            "appCommandMetadata": {
                "appCommandId": 7,
                "appCommandType": "MESSAGE_ACTION",
            },
        }
    )


async def test_stable_command_kinds_have_distinct_observers() -> None:
    router = Router()

    @router.slash_command()
    async def slash(event: CommandEvent) -> CommandKind | None:
        return event.kind

    @router.quick_command()
    async def quick(event: CommandEvent) -> CommandKind | None:
        return event.kind

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    slash_event = parse_interaction(
        {
            "type": "MESSAGE",
            "message": {"slashCommand": {"commandId": "1"}, "text": "/x"},
        }
    )
    quick_event = parse_interaction(
        {
            "type": "APP_COMMAND",
            "appCommandMetadata": {
                "appCommandId": 2,
                "appCommandType": "QUICK_COMMAND",
            },
        }
    )

    assert await dispatcher.feed_update(slash_event) is CommandKind.SLASH_COMMAND
    assert await dispatcher.feed_update(quick_event) is CommandKind.QUICK_COMMAND


async def test_message_action_is_not_typed_without_preview_enrollment() -> None:
    router = Router()
    typed_calls: list[str] = []

    @router.message_action()
    async def message_action(event: CommandEvent) -> str:
        typed_calls.append("message_action")
        return "typed"

    @router.command()
    async def command(event: CommandEvent) -> str:
        typed_calls.append("command")
        return "command"

    @router.event()
    async def raw_fallback(event: Event) -> str:
        assert isinstance(event, CommandEvent)
        return "raw"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(_message_action()) == "raw"
    assert typed_calls == []


async def test_message_action_typed_routing_requires_explicit_preview() -> None:
    router = Router()

    @router.message_action()
    async def message_action(
        event: CommandEvent,
        preview_capabilities: PreviewCapabilities,
    ) -> str:
        preview_capabilities.require(PreviewFeature.MESSAGE_ACTION)
        assert event.kind is CommandKind.MESSAGE_ACTION
        return "enabled"

    dispatcher = Dispatcher(preview_features={PreviewFeature.MESSAGE_ACTION})
    dispatcher.include_router(router)

    assert await dispatcher.feed_update(_message_action()) == "enabled"


async def test_caller_context_cannot_bypass_preview_enrollment() -> None:
    router = Router()

    @router.message_action()
    async def message_action(event: CommandEvent) -> str:
        return "typed"

    @router.event()
    async def fallback(event: Event) -> str:
        return "raw"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    forged = PreviewCapabilities({PreviewFeature.MESSAGE_ACTION})

    assert (
        await dispatcher.feed_update(_message_action(), preview_capabilities=forged)
        == "raw"
    )
