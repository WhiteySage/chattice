"""Card sync-response branches in the FastAPI integration."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import ActionEvent, MessageEvent, WidgetUpdatedEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import MockVerifier, WidgetAutocomplete


def _card() -> Card:
    return Card(
        header=CardHeader(title="T"), sections=[Section(widgets=[TextParagraph("hi")])]
    )


def _message_payload(text: str) -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": text},
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
    }


async def test_message_handler_returns_cards_v2() -> None:
    router = Router()

    @router.message()
    async def home(message: MessageEvent) -> Card:
        return _card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    body = result.json()
    assert "cardsV2" in body
    assert body["cardsV2"][0]["card"]["header"]["title"] == "T"


async def test_card_clicked_handler_returns_update_message() -> None:
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> Card:
        return _card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/CARD", "sender": {"type": "BOT"}},
        "common": {
            "invokedFunction": "deploy.confirm",
            "parameters": {"env": "prod"},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"] == {"type": "UPDATE_MESSAGE"}
    assert body["cardsV2"][0]["card"]["header"]["title"] == "T"


async def test_card_clicked_on_human_message_updates_user_cards() -> None:
    """Documented sender rule: a click on a card attached to a HUMAN message
    answers with UPDATE_USER_MESSAGE_CARDS, not UPDATE_MESSAGE."""
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> Card:
        assert action.sender_type == "HUMAN"
        return _card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "message": {"name": "spaces/AAA/messages/CARD", "sender": {"type": "HUMAN"}},
        "common": {
            "invokedFunction": "deploy.confirm",
            "parameters": {"env": "prod"},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"] == {"type": "UPDATE_USER_MESSAGE_CARDS"}


async def test_card_clicked_without_sender_type_is_rejected() -> None:
    """Never guess the response type from insufficient event data."""
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> Card:
        return _card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "common": {
            "invokedFunction": "deploy.confirm",
            "parameters": {"env": "prod"},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 500


async def test_matched_url_message_returns_update_user_message_cards() -> None:
    """Link previews: a card answering a message with a matched URL must use
    UPDATE_USER_MESSAGE_CARDS."""
    router = Router()

    @router.message()
    async def preview(message: MessageEvent) -> Card:
        assert message.matched_url == "https://example.com/ticket/42"
        return _card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    payload = {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "message": {
            "name": "spaces/AAA/messages/2",
            "text": "https://example.com/ticket/42",
            "matchedUrl": {"url": "https://example.com/ticket/42"},
            "sender": {"type": "HUMAN"},
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"] == {"type": "UPDATE_USER_MESSAGE_CARDS"}
    assert "cardsV2" in body


async def test_widget_autocomplete_response() -> None:
    """UPDATE_WIDGET: autocomplete suggestions for a WIDGET_UPDATED query."""
    router = Router()

    @router.widget_updated()
    async def autocomplete(event: WidgetUpdatedEvent) -> WidgetAutocomplete:
        return WidgetAutocomplete(widget_id="contacts", suggestions=("Kai", "Katya"))

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    payload = {
        "type": "WIDGET_UPDATED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "common": {
            "invokedFunction": "search.contacts",
            "parameters": {"autocomplete_widget_query": "Kai"},
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"] == {
        "type": "UPDATE_WIDGET",
        "updatedWidget": {
            "widget": "contacts",
            "suggestions": {"items": [{"text": "Kai"}, {"text": "Katya"}]},
        },
    }


async def test_widget_autocomplete_on_wrong_event_is_rejected() -> None:
    router = Router()

    @router.message()
    async def wrong(message: MessageEvent) -> WidgetAutocomplete:
        return WidgetAutocomplete(widget_id="w")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 500
