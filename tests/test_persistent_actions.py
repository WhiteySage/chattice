"""Persistent/stateless actions: routing survives process restart (B7)."""

from __future__ import annotations

from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Button, ButtonList, Card, CardHeader, Section
from chattice.events import ActionEvent


def _card_with_action() -> tuple[Card, dict[str, object]]:
    """Build a card and derive the documented CARD_CLICKED payload for it —
    the payload a RESTARTED process would receive."""
    card = Card(
        header=CardHeader(title="Invoice #7"),
        sections=[
            Section(
                widgets=[
                    ButtonList(
                        buttons=[
                            Button(
                                "Approve",
                                action="invoice.approve",
                                parameters={"id": "7"},
                            )
                        ]
                    )
                ]
            )
        ],
    )
    serialized = card.to_dict()
    button = serialized["sections"][0]["widgets"][0]["buttonList"]["buttons"][0]
    action = button["onClick"]["action"]
    payload: dict[str, object] = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/1", "sender": {"type": "BOT"}},
        "common": {
            "invokedFunction": action["function"],
            "parameters": dict((p["key"], p["value"]) for p in action["parameters"]),
        },
    }
    return card, payload


def _build_app() -> Dispatcher:
    router = Router()

    @router.action("invoice.approve")
    async def approve(event: ActionEvent) -> str:
        return f"approved {event.parameters['id']}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def test_action_routes_after_fresh_application() -> None:
    """The invariant behind persistent actions: routing keys on the STABLE
    action function string echoed by Google, never on in-memory objects —
    a freshly built dispatcher (post-restart) resolves the same button."""
    _, payload = _card_with_action()

    # "process restart": drop the old app entirely, build a brand-new one
    first = _build_app()
    assert (
        await first.feed_update(cast(ActionEvent, parse_interaction(payload)))
        == "approved 7"
    )

    second = _build_app()
    assert (
        await second.feed_update(cast(ActionEvent, parse_interaction(payload)))
        == "approved 7"
    )


async def test_card_from_old_version_still_routes() -> None:
    """A payload replayed from a card built by an older app version (same
    stable function name) keeps routing."""
    card, _ = _card_with_action()
    # simulate the old version's serialization
    old_payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-15T09:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/OLD", "sender": {"type": "BOT"}},
        "common": {
            "invokedFunction": "invoice.approve",
            "parameters": {"id": "7"},
        },
    }
    app = _build_app()
    assert (
        await app.feed_update(cast(ActionEvent, parse_interaction(old_payload)))
        == "approved 7"
    )
    assert card is not None
