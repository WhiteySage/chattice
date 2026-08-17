"""Phase gate: Card -> button -> CARD_CLICKED -> router.action (no raw JSON)."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    Button,
    ButtonList,
    Card,
    CardHeader,
    Section,
    TextParagraph,
)
from chattice.events import ActionEvent


async def test_card_button_to_action_round_trip() -> None:
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
                            ),
                            Button("Cancel", action="deploy.cancel"),
                        ]
                    ),
                ]
            )
        ],
    )
    serialized = card.to_dict()
    button = serialized["sections"][0]["widgets"][1]["buttonList"]["buttons"][0]
    action = button["onClick"]["action"]

    # A documented CARD_CLICKED interaction for that button:
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "action": {
            "actionMethodName": action["function"],
            "parameters": [
                {"key": p["key"], "value": p["value"]} for p in action["parameters"]
            ],
        },
        "common": {
            "invokedFunction": action["function"],
            "parameters": {p["key"]: p["value"] for p in action["parameters"]},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }

    router = Router()
    seen: list[tuple[str, dict[str, object]]] = []

    @router.action("deploy.confirm")
    async def confirm(action_event: ActionEvent) -> str:
        seen.append((action_event.function_name or "", dict(action_event.parameters)))
        return "confirmed"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    event = parse_interaction(payload)
    result = await dispatcher.feed_update(event)
    assert result == "confirmed"
    assert seen == [("deploy.confirm", {"env": "prod"})]
