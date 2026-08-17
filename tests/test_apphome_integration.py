"""App Home RenderActions branches (wrapped envelope)."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import AppHomeEvent, FormSubmitEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import MockVerifier


def _app_home_payload() -> dict[str, object]:
    return {
        "chat": {
            "type": "APP_HOME",
            "user": {"name": "users/123"},
            # Live wire shape (2026-08-16): the Home DM space carries
            # singleUserBotDm + spaceType — parsed into SpaceRef.
            "space": {
                "name": "spaces/DM",
                "singleUserBotDm": True,
                "spaceType": "DIRECT_MESSAGE",
            },
        },
        "commonEventObject": {
            "userLocale": "en-US",
            "timeZone": {"id": "UTC", "offset": 0},
        },
    }


def _submit_form_payload() -> dict[str, object]:
    return {
        "chat": {
            "type": "SUBMIT_FORM",
            "user": {"name": "users/123"},
            "space": {"name": "spaces/DM"},
        },
        "commonEventObject": {
            "invokedFunction": "update.home",
            "userLocale": "en-US",
            "timeZone": {"id": "UTC", "offset": 0},
        },
    }


def _home_card() -> Card:
    return Card(
        header=CardHeader(title="Home"),
        sections=[Section(widgets=[TextParagraph("Welcome")])],
    )


async def test_app_home_returns_push_card() -> None:
    router = Router()

    @router.app_home()
    async def home(event: AppHomeEvent) -> Card:
        # The Home DM space must be distinguishable from collaborative
        # spaces (never a publish destination).
        assert event.space is not None
        assert event.space.single_user_bot_dm is True
        assert event.space.space_type == "DIRECT_MESSAGE"
        return _home_card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_app_home_payload())
    assert result.status_code == 200
    body = result.json()
    assert body == {
        "action": {
            "navigations": [
                {
                    "pushCard": {
                        "header": {"title": "Home"},
                        "sections": [
                            {"widgets": [{"textParagraph": {"text": "Welcome"}}]}
                        ],
                    }
                }
            ]
        }
    }


async def test_submit_form_returns_update_card() -> None:
    router = Router()

    @router.form_submit()
    async def update(event: FormSubmitEvent) -> Card:
        return _home_card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_submit_form_payload())
    assert result.status_code == 200
    body = result.json()
    # Documented update shape: renderActions wrapper for home-card updates
    assert (
        body["renderActions"]["action"]["navigations"][0]["updateCard"]["header"][
            "title"
        ]
        == "Home"
    )
