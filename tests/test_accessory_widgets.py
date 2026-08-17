"""Accessory widgets (B2): facade, Bot integration, same action router."""

from __future__ import annotations

from typing import cast

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.cards import AccessoryWidget, Button, ButtonList
from chattice.client import Bot
from chattice.events import ActionEvent
from tests.client._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _widget() -> AccessoryWidget:
    return AccessoryWidget(
        button_list=ButtonList(
            buttons=[
                Button("Approve", action="invoice.approve", parameters={"id": "7"})
            ]
        )
    )


def test_accessory_widget_proto_round_trip() -> None:
    proto = _widget().to_proto()
    assert proto.button_list.buttons[0].text == "Approve"
    assert proto.button_list.buttons[0].on_click.action.function == "invoice.approve"


def test_accessory_widget_to_dict_shape() -> None:
    payload = _widget().to_dict()
    # F11: loadIndicator is written explicitly (NONE when unset) — the
    # SDK enum has no unspecified value, so an explicit NONE is what
    # keeps the wire round-trip lossless.
    assert payload == {
        "buttonList": {
            "buttons": [
                {
                    "text": "Approve",
                    "onClick": {
                        "action": {
                            "function": "invoice.approve",
                            "parameters": [{"key": "id", "value": "7"}],
                            "loadIndicator": "NONE",
                        }
                    },
                }
            ]
        }
    }


async def test_bot_send_message_attaches_accessory_widgets() -> None:
    creds = _creds()
    transport = FakeChatTransport(credentials=creds)
    bot = Bot(credentials=creds, transport=transport, auth_mode=AuthMode.APP)
    await bot.send_message("spaces/AAA", text="Invoice", accessory_widgets=[_widget()])
    request = transport.requests[-1]
    assert len(request.message.accessory_widgets) == 1
    assert (
        request.message.accessory_widgets[0]
        .button_list.buttons[0]
        .on_click.action.function
        == "invoice.approve"
    )


async def test_user_auth_rejects_accessory_widgets() -> None:
    """Documented Google rule: accessory widgets require app auth."""
    creds = _creds()
    bot = Bot(credentials=creds, auth_mode=AuthMode.USER)
    with pytest.raises(CapabilityNotSupported, match="app authentication"):
        await bot.send_message("spaces/AAA", text="x", accessory_widgets=[_widget()])


async def test_accessory_click_routes_through_the_same_action_observer() -> None:
    """Accessory clicks arrive as CARD_CLICKED with the same function +
    parameters: they reuse ActionEvent and router.action — no second
    callback subsystem."""
    router = Router()

    @router.action("invoice.approve")
    async def approve(event: ActionEvent) -> str:
        return f"approved {event.parameters['id']}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/1", "sender": {"type": "BOT"}},
        "common": {
            "invokedFunction": "invoice.approve",
            "parameters": {"id": "7"},
        },
    }
    event = cast(ActionEvent, parse_interaction(payload))
    assert await dispatcher.feed_update(event) == "approved 7"
