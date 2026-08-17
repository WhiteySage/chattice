"""Raw escape hatches and surface validation (B6)."""

from __future__ import annotations

import pytest

from chattice import Dispatcher, Router
from chattice.cards import (
    Card,
    DateTimePicker,
    Dialog,
    RawWidget,
    Section,
    TextParagraph,
)
from chattice.events import MessageEvent, RemovedFromSpaceEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import MockVerifier, RawInteractionResponse


def test_raw_widget_round_trips_losslessly() -> None:
    payload = {
        "decoratedText": {"text": "Future widget", "wrapText": True},
        "horizontalAlignment": "CENTER",
    }
    widget = RawWidget(payload)
    assert widget.to_dict() == payload
    # inside a card the payload survives the JSON path verbatim
    card = Card(sections=[Section(widgets=[widget])])
    rendered = card.to_dict()
    rendered_widgets = rendered["sections"][0]["widgets"]
    assert rendered_widgets == [payload]


def test_raw_widget_invalid_known_field_raises() -> None:
    with pytest.raises(ValueError, match="valid Cards v2 widget"):
        RawWidget({"textParagraph": {"text": 42}})  # text must be a string


def test_dialog_rejects_datetime_picker() -> None:
    card = Card(
        sections=[
            Section(
                widgets=[
                    DateTimePicker(name="when", label="When"),
                ]
            )
        ]
    )
    with pytest.raises(ValueError, match="DateTimePicker"):
        Dialog(body=card)


def test_dialog_allows_regular_widgets() -> None:
    card = Card(sections=[Section(widgets=[TextParagraph("ok")])])
    dialog = Dialog(body=card)
    assert dialog.to_dict()["dialog"]["body"]["sections"][0]["widgets"] == [
        {"textParagraph": {"text": "ok"}}
    ]


async def test_removed_from_space_cannot_respond() -> None:
    router = Router()

    @router.removed_from_space()
    async def removed(event: RemovedFromSpaceEvent) -> str:
        return "must-not-serialize"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = __import__("fastapi").FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    import httpx

    payload = {
        "type": "REMOVED_FROM_SPACE",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 500  # never serialized into a message


async def test_raw_interaction_response_passes_through() -> None:
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> RawInteractionResponse:
        return RawInteractionResponse(payload={"customFutureField": {"anything": True}})

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = __import__("fastapi").FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/",
            json={
                "type": "MESSAGE",
                "message": {"text": "hi"},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            },
        )
    assert result.status_code == 200
    assert result.json() == {"customFutureField": {"anything": True}}


async def test_raw_interaction_response_blocked_for_removed_from_space() -> None:
    router = Router()

    @router.removed_from_space()
    async def removed(event: RemovedFromSpaceEvent) -> RawInteractionResponse:
        return RawInteractionResponse(payload={"text": "x"})

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = __import__("fastapi").FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    import httpx

    payload = {
        "type": "REMOVED_FROM_SPACE",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 500
