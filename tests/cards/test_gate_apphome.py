"""Gate: APP_HOME wrapped envelope -> app_home -> Card (pushCard);

SUBMIT_FORM -> updateCard.
"""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import AppHomeEvent, FormSubmitEvent


def _home_card() -> Card:
    return Card(
        header=CardHeader(title="Home"),
        sections=[Section(widgets=[TextParagraph("Welcome")])],
    )


async def test_app_home_cycle_without_raw_json() -> None:
    router = Router()

    @router.app_home()
    async def home(event: AppHomeEvent) -> Card:
        return _home_card()

    @router.form_submit()
    async def update(event: FormSubmitEvent) -> Card:
        return _home_card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    home_event = parse_interaction(
        {
            "chat": {
                "type": "APP_HOME",
                "user": {"name": "users/123"},
                "space": {"name": "spaces/DM"},
            },
            "commonEventObject": {
                "userLocale": "en-US",
                "timeZone": {"id": "UTC", "offset": 0},
            },
        }
    )
    card = await dispatcher.feed_update(home_event)
    assert card == _home_card()

    submit_event = parse_interaction(
        {
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
    )
    card2 = await dispatcher.feed_update(submit_event)
    assert card2 == _home_card()
