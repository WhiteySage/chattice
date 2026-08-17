"""F08 regression: dialog envelope, routing, capabilities, serialization
agree on ONE predicate (can_open_dialog)."""

from __future__ import annotations

from typing import cast

import pytest
from starlette.applications import Starlette

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.adapters.google_chat.exceptions import InvalidInteractionPayload
from chattice.capabilities import (
    ResponseCapabilities,
    ResponseCapability,
    can_open_dialog,
)
from chattice.cards import Card, Dialog
from chattice.events import (
    ActionEvent,
    CommandEvent,
    DialogEventType,
    DialogMetadata,
    Event,
    FormSubmitEvent,
    MessageEvent,
)
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import MockVerifier


def _event(payload: dict[str, object]) -> Event:
    return parse_interaction(payload)


def _base_payload(event_type: str) -> dict[str, object]:
    return {
        "type": event_type,
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
    }


def _command_payload() -> dict[str, object]:
    payload = _base_payload("MESSAGE")
    payload["message"] = {
        "text": "ping",
        "slashCommand": {"commandId": "1"},
        "argumentText": " ping",
    }
    return payload


def _action_payload(dialog: dict[str, object] | None) -> dict[str, object]:
    payload = _base_payload("CARD_CLICKED")
    payload["common"] = {"invokedFunction": "card.clicked"}
    if dialog is not None:
        payload["dialog"] = dialog
    return payload


# ---------------------------------------------------------------- parsing


def test_false_flag_with_type_rejected_at_parse() -> None:
    payload = _base_payload("MESSAGE")
    payload["message"] = {"text": "x"}
    payload["isDialogEvent"] = False
    payload["dialogEventType"] = "SUBMIT_DIALOG"
    with pytest.raises(InvalidInteractionPayload):
        parse_interaction(payload)


def test_true_flag_without_type_rejected_at_parse() -> None:
    payload = _base_payload("MESSAGE")
    payload["message"] = {"text": "x"}
    payload["isDialogEvent"] = True
    with pytest.raises(InvalidInteractionPayload):
        parse_interaction(payload)


def test_consistent_dialog_envelope_parses() -> None:
    payload = _action_payload(None)
    payload["isDialogEvent"] = True
    payload["dialogEventType"] = "REQUEST_DIALOG"
    event = _event(payload)
    assert isinstance(event, ActionEvent)
    assert event.dialog is not None
    assert event.dialog.type == DialogEventType.REQUEST_DIALOG


# ------------------------------------------------------------ capabilities


@pytest.mark.parametrize(
    "event_factory,want",
    [
        (
            lambda: cast(
                Event,
                CommandEvent(
                    command_id=1,
                    dialog=DialogMetadata(type=DialogEventType.REQUEST_DIALOG),
                ),
            ),
            True,
        ),
        (lambda: cast(Event, CommandEvent(command_id=1)), True),
        (
            lambda: cast(
                Event,
                ActionEvent(dialog=DialogMetadata(type=DialogEventType.REQUEST_DIALOG)),
            ),
            True,
        ),
        (
            lambda: cast(
                Event,
                ActionEvent(dialog=DialogMetadata(type=DialogEventType.SUBMIT_DIALOG)),
            ),
            False,
        ),
        (
            lambda: cast(
                Event,
                ActionEvent(dialog=DialogMetadata(type=DialogEventType.CANCEL_DIALOG)),
            ),
            False,
        ),
        (lambda: cast(Event, ActionEvent()), False),
        (lambda: cast(Event, MessageEvent(text="hi")), False),
        (lambda: cast(Event, FormSubmitEvent()), False),
        (lambda: None, False),
    ],
)
def test_can_open_dialog_truth_table(event_factory: object, want: bool) -> None:
    event = event_factory()  # type: ignore[operator]
    assert can_open_dialog(event) is want
    capabilities = ResponseCapabilities.resolve(transport="http", event=event)
    assert (ResponseCapability.DIALOGS in capabilities) is want


# ----------------------------------------------------------- serialization


def _app_returning_dialog() -> Starlette:
    router = Router()

    @router.message()
    async def handler(event: object) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = Starlette(routes=create_chat_router(dispatcher, MockVerifier()).routes)
    return app


async def test_command_event_can_return_dialog() -> None:
    import httpx

    router = Router()

    @router.command()
    async def handler(event: CommandEvent) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = Starlette(routes=create_chat_router(dispatcher, MockVerifier()).routes)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_command_payload())
    assert result.status_code == 200
    assert result.json()["actionResponse"]["type"] == "DIALOG"


async def test_plain_message_dialog_response_is_500() -> None:
    import httpx

    router = Router()

    @router.message()
    async def handler(event: MessageEvent) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = Starlette(routes=create_chat_router(dispatcher, MockVerifier()).routes)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/", json={**_base_payload("MESSAGE"), "message": {"text": "x"}}
        )
    assert result.status_code == 500


async def test_submit_dialog_action_cannot_return_new_dialog() -> None:
    import httpx

    router = Router()

    @router.dialog_submit()
    async def handler(event: ActionEvent) -> Dialog:
        return Dialog(body=Card())

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = Starlette(routes=create_chat_router(dispatcher, MockVerifier()).routes)
    payload = _action_payload(
        {
            "isDialogEvent": True,
            "dialogEventType": "SUBMIT_DIALOG",
        }
    )
    # the adapter model reads the top-level envelope flags; move them
    payload["isDialogEvent"] = True
    payload["dialogEventType"] = "SUBMIT_DIALOG"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 500
