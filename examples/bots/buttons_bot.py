"""Buttons bot: Card -> CARD_CLICKED -> @router.action() (no network).

Builds a Card with a button list, derives the documented CARD_CLICKED
payload from the serialized card itself (
tests/cards/test_gate.py), and routes it into a named-action handler with its
parameters intact.

Run:
    python examples/bots/buttons_bot.py
"""

from __future__ import annotations

import asyncio

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


async def main() -> None:
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

    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action_event: ActionEvent) -> str:
        return f"deploying {action_event.parameters['env']}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    # The documented CARD_CLICKED payload for the first card button.
    serialized = card.to_dict()
    button = serialized["sections"][0]["widgets"][1]["buttonList"]["buttons"][0]
    action = button["onClick"]["action"]
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
    result = await dispatcher.feed_update(parse_interaction(payload))
    print(f"button click -> {result}")


if __name__ == "__main__":
    asyncio.run(main())
