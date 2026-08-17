"""Command bot: Google command families -> typed observers (no network).

Google delivers commands through two wire families, and the adapter
normalizes BOTH into `CommandEvent`:
- slash commands arrive as `MESSAGE` events with `message.slashCommand`
  (numeric command id as an int64 string) + `argumentText` (the
  mention-stripped body) — `CommandKind.SLASH_COMMAND`;
- quick commands / message actions arrive as `APP_COMMAND` events with
  `appCommandMetadata` — `CommandKind.QUICK_COMMAND` (MESSAGE_ACTION is a
  Developer Preview type and needs explicit dispatcher enrollment).

Run:
    python examples/bots/command_bot.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import CommandEvent

# Documented slash-command payload (MESSAGE + slashCommand + argumentText),
# mirrors tests/fixtures/google_chat/interactions/slash_command.json.
_SLASH_PAYLOAD = {
    "type": "MESSAGE",
    "eventTime": "2026-08-15T10:00:00Z",
    "user": {"name": "users/123"},
    "space": {"name": "spaces/AAA"},
    "message": {
        "name": "spaces/AAA/messages/1",
        "argumentText": "deploy prod",
        "text": "/deploy prod",
        "slashCommand": {"commandId": "42"},
        "sender": {"name": "users/123", "type": "HUMAN"},
    },
}

# Documented quick-command payload (APP_COMMAND + appCommandMetadata),
# mirrors tests/fixtures/google_chat/interactions/app_command.json.
_QUICK_PAYLOAD = {
    "type": "APP_COMMAND",
    "eventTime": "2026-08-13T12:36:00Z",
    "message": {"name": "spaces/AAA/messages/CMD", "text": "/deploy prod"},
    "user": {"name": "users/123"},
    "space": {"name": "spaces/AAA"},
    "appCommandMetadata": {"appCommandId": 42, "appCommandType": "QUICK_COMMAND"},
}


async def main() -> None:
    router = Router()

    @router.slash_command()
    async def slash_deploy(event: CommandEvent) -> str:
        return (
            f"command={event.command_id} kind={event.kind} text={event.message_text!r}"
        )

    @router.quick_command()
    async def quick_deploy(event: CommandEvent) -> str:
        return f"command={event.command_id} kind={event.kind}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    slash = await dispatcher.feed_update(parse_interaction(_SLASH_PAYLOAD))
    quick = await dispatcher.feed_update(parse_interaction(_QUICK_PAYLOAD))
    print(f"slash command -> {slash}")
    print(f"quick command -> {quick}")


if __name__ == "__main__":
    asyncio.run(main())
