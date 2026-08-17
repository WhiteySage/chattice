"""dialog_submit / dialog_cancel observers."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import ActionEvent, DialogEventType


def _payload(dialog_type: str) -> dict[str, object]:
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


async def test_dialog_submit_routes() -> None:
    router = Router()
    seen: list[str] = []

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> str:
        assert event.dialog is not None
        assert isinstance(event.dialog.type, DialogEventType)
        seen.append(event.dialog.type.value)
        return "submitted"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(parse_interaction(_payload("SUBMIT_DIALOG")))
    assert result == "submitted"
    assert seen == ["SUBMIT_DIALOG"]


async def test_dialog_cancel_routes() -> None:
    router = Router()
    seen: list[str] = []

    @router.dialog_cancel()
    async def cancel(event: ActionEvent) -> None:
        assert event.dialog is not None
        assert isinstance(event.dialog.type, DialogEventType)
        seen.append(event.dialog.type.value)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.feed_update(parse_interaction(_payload("CANCEL_DIALOG")))
    assert seen == ["CANCEL_DIALOG"]


async def test_plain_card_clicked_does_not_hit_dialog_observers() -> None:
    router = Router()
    seen: list[str] = []

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> str:
        seen.append("submit")
        return "x"

    @router.dialog_cancel()
    async def cancel(event: ActionEvent) -> None:
        seen.append("cancel")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
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
    result = await dispatcher.feed_update(parse_interaction(payload))
    assert result is None
    assert seen == []
