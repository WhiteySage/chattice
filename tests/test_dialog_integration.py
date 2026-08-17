"""Dialog sync-response branches."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.cards import (
    ActionStatus,
    Card,
    CardHeader,
    Dialog,
    Section,
    TextParagraph,
)
from chattice.events import ActionEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import MockVerifier


def _dialog_payload(dialog_type: str) -> dict[str, object]:
    return {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "isDialogEvent": True,
        "dialogEventType": dialog_type,
        "common": {
            "invokedFunction": "open.contact",
            "formInputs": {"name": {"stringInputs": {"value": ["Иван"]}}},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }


async def test_request_dialog_returns_dialog_response() -> None:
    router = Router()

    @router.action("open.contact")
    async def open_dialog(action: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(
                header=CardHeader(title="New contact"),
                sections=[Section(widgets=[TextParagraph("Enter details")])],
            )
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_dialog_payload("REQUEST_DIALOG"))
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"]["type"] == "DIALOG"
    assert (
        body["actionResponse"]["dialogAction"]["dialog"]["body"]["header"]["title"]
        == "New contact"
    )


async def test_submit_dialog_returns_action_status() -> None:
    router = Router()

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> ActionStatus:
        return ActionStatus.ok("Saved")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_dialog_payload("SUBMIT_DIALOG"))
    assert result.status_code == 200
    body = result.json()
    assert body["actionResponse"]["type"] == "DIALOG"
    assert body["actionResponse"]["dialogAction"]["actionStatus"] == {
        "statusCode": "OK",
        "userFacingMessage": "Saved",
    }


async def test_cancel_dialog_with_none_returns_empty_200() -> None:
    router = Router()

    @router.dialog_cancel()
    async def cancel(event: ActionEvent) -> None:
        return None

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_dialog_payload("CANCEL_DIALOG"))
    assert result.status_code == 200
    assert result.content == b""


async def test_dialog_response_on_plain_click_returns_500() -> None:
    """Dialog outside a dialog interaction is an application bug (spec §6)."""
    router = Router()

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> Dialog:
        return Dialog(body=Card(header=CardHeader(title="T")))

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    plain_click = {
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
        result = await client.post("/", json=plain_click)
    assert result.status_code == 500


async def test_action_status_on_request_dialog_returns_500() -> None:
    """ActionStatus is only valid for SUBMIT_DIALOG (spec §6)."""
    router = Router()

    @router.action("open.contact")
    async def open_dialog(action: ActionEvent) -> ActionStatus:
        return ActionStatus.ok("nope")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_dialog_payload("REQUEST_DIALOG"))
    assert result.status_code == 500
