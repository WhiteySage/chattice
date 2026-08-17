"""App Home dashboard: APP_HOME -> RenderActions pushCard; form -> updateCard.

Google's App Home: the Home tab sends APP_HOME, the app answers with a
card navigation; widget interactions arrive as SUBMIT_FORM and refresh
the card with updateCard.

Run:
    uv run python examples/scenarios/apphome_dashboard.py
"""

from __future__ import annotations

import asyncio
from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import AppHomeEvent, FormSubmitEvent

TICKETS = {"open": 12, "closed": 340}


def dashboard_card(open_count: int) -> Card:
    return Card(
        header=CardHeader(title="Dashboard"),
        sections=[Section(widgets=[TextParagraph(f"Открытых заявок: {open_count}")])],
    )


async def main() -> None:
    router = Router()

    @router.app_home()
    async def home(event: AppHomeEvent) -> Card:
        return dashboard_card(TICKETS["open"])

    @router.form_submit()
    async def refresh(event: FormSubmitEvent) -> Card:
        TICKETS["open"] -= 1
        return dashboard_card(TICKETS["open"])

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    home_payload = {
        "type": "APP_HOME",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/DM"},
    }
    card = await dispatcher.feed_update(parse_interaction(home_payload))
    print("home card:", cast(Card, card).to_dict()["sections"][0]["widgets"][0])
    form_payload = {
        "type": "SUBMIT_FORM",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/DM"},
        "common": {
            "invokedFunction": "tickets.refresh",
            "parameters": {"action": "close"},
        },
    }
    updated = await dispatcher.feed_update(parse_interaction(form_payload))
    print("updated card:", cast(Card, updated).to_dict()["sections"][0]["widgets"][0])


if __name__ == "__main__":
    asyncio.run(main())
