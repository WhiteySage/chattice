"""Live integration smoke tests — real Google Chat calls when enabled.

Network tests require:
    CHATTICE_GOOGLE_CREDENTIALS=/path/to/service-account.json
    CHATTICE_GOOGLE_SPACE=spaces/AAA
    pytest tests/integration/live -m google_live

Contract tests (card round-trip, command payloads, Workspace Pub/Sub
replay) execute in the same run and do NOT need network access. Every
test in this suite EXECUTES when run — none raise NotImplementedError.
See README.md for the full setup.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pytest

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.cards import (
    Button,
    ButtonList,
    Card,
    CardHeader,
    Section,
    TextParagraph,
)
from chattice.client import Bot
from chattice.events import ActionEvent, CommandEvent
from chattice.workspace_events import parse_workspace_envelope

pytestmark = pytest.mark.google_live

_CREDENTIALS_ENV = "CHATTICE_GOOGLE_CREDENTIALS"
_SPACE_ENV = "CHATTICE_GOOGLE_SPACE"


def _require_network_env() -> tuple[str, str]:
    path = os.environ.get(_CREDENTIALS_ENV)
    space = os.environ.get(_SPACE_ENV)
    if not path or not space:
        pytest.skip(f"set {_CREDENTIALS_ENV} and {_SPACE_ENV} for live calls")
    return path, space


def _load_fixture(name: str) -> dict[str, object]:
    base = Path(__file__).parents[2] / "fixtures" / "google_chat" / "interactions"
    return json.loads((base / name).read_text())  # type: ignore[no-any-return]


# --- network tests (skip without credentials) ---


async def test_message_send_update_delete() -> None:
    path, space = _require_network_env()
    provider = ServiceAccountCredentialsProvider.from_service_account_file(path)
    async with Bot(credentials_provider=provider) as bot:
        created = await bot.send_message(space, text="chattice live smoke")
        assert created.name
        updated = await bot.update_message(created.name, text="chattice live smoke v2")
        assert updated.name == created.name
        await bot.delete_message(created.name)


async def test_echo_round_trip_via_bot() -> None:
    path, space = _require_network_env()
    provider = ServiceAccountCredentialsProvider.from_service_account_file(path)
    async with Bot(credentials_provider=provider) as bot:
        created = await bot.send_message(space, text="echo-ping")
        fetched = await bot.get_message(created.name)
        assert fetched.name == created.name


# --- contract tests (no network; execute in the live run) ---


async def test_card_button_round_trip() -> None:
    """Card -> serialized JSON -> CARD_CLICKED payload -> handler."""
    card = Card(
        header=CardHeader(title="Deploy production?"),
        sections=[
            Section(
                widgets=[
                    TextParagraph("Deploy v2.1?"),
                    ButtonList(
                        buttons=[
                            Button(
                                "Deploy",
                                action="deploy.confirm",
                                parameters={"env": "prod"},
                            )
                        ]
                    ),
                ]
            )
        ],
    )
    serialized = card.to_dict()
    button = serialized["sections"][0]["widgets"][1]["buttonList"]["buttons"][0]
    action = button["onClick"]["action"]
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/CARD", "sender": {"type": "BOT"}},
        "action": {
            "actionMethodName": action["function"],
            "parameters": [
                {"key": p["key"], "value": p["value"]} for p in action["parameters"]
            ],
        },
        "common": {
            "invokedFunction": action["function"],
            "parameters": {p["key"]: p["value"] for p in action["parameters"]},
        },
    }
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(event: ActionEvent) -> str:
        return f"deploying {event.parameters['env']}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(parse_interaction(payload))
    assert result == "deploying prod"


async def test_command_payloads_parse() -> None:
    """Both command wire families normalize to CommandEvent."""
    slash = parse_interaction(_load_fixture("slash_command.json"))
    quick = parse_interaction(_load_fixture("app_command.json"))
    assert isinstance(slash, CommandEvent)
    assert isinstance(quick, CommandEvent)
    assert slash.source_kind == "SLASH_COMMAND"
    assert quick.source_kind == "QUICK_COMMAND"


async def test_workspace_pubsub_replay() -> None:
    """Official Workspace Events Pub/Sub binding replays end-to-end."""
    data = json.dumps({"message": {"name": "spaces/AAA/messages/B"}}).encode()
    envelope = {
        "message": {
            "data": base64.b64encode(data).decode(),
            "messageId": "m-live",
            "attributes": {
                "ce-id": "evt-live",
                "ce-source": "//chat.googleapis.com/spaces/AAA",
                "ce-specversion": "1.0",
                "ce-time": "2026-08-15T10:00:00Z",
                "ce-type": "google.workspace.chat.message.v1.created",
            },
        },
        "subscription": "projects/p/subscriptions/s",
    }
    event = parse_workspace_envelope(envelope)
    assert event.event_id == "evt-live"
    assert event.data["message"] == {"name": "spaces/AAA/messages/B"}
