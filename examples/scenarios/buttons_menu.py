"""Multi-level button menu: the inline-keyboard release blocker (§14.9).

Google-native equivalent of a Telegram inline menu: a Card with buttons,
each click answered by a NEW card via the sender-aware UPDATE_MESSAGE
response, using STABLE action identities (deploy.*, menu.back) — the
menu survives restarts by construction.

Run:
    uv run python examples/scenarios/buttons_menu.py
"""

from __future__ import annotations

import asyncio
from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Button, ButtonList, Card, CardHeader, Section
from chattice.events import ActionEvent


def menu_card(title: str, buttons: list[tuple[str, str]]) -> Card:
    return Card(
        header=CardHeader(title=title),
        sections=[
            Section(
                widgets=[
                    ButtonList(
                        buttons=[
                            Button(label, action=action) for label, action in buttons
                        ]
                    )
                ]
            )
        ],
    )


async def main() -> None:
    router = Router()

    @router.action("menu.root")
    async def root(event: ActionEvent) -> Card:
        return menu_card(
            "Главное меню",
            [("Заявки", "menu.tickets"), ("Отчёты", "menu.reports")],
        )

    @router.action("menu.tickets")
    async def tickets(event: ActionEvent) -> Card:
        return menu_card(
            "Заявки",
            [
                ("Создать", "tickets.create"),
                ("Мои", "tickets.mine"),
                ("Назад", "menu.root"),
            ],
        )

    @router.action("tickets.create")
    async def create(event: ActionEvent) -> Card:
        return menu_card("Создать заявку", [("Готово", "menu.root")])

    @router.action("tickets.mine")
    async def mine(event: ActionEvent) -> Card:
        return menu_card("Мои заявки: 2", [("Назад", "menu.tickets")])

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    def click(action_name: str) -> ActionEvent:
        from typing import cast

        return cast(
            ActionEvent,
            parse_interaction(
                {
                    "type": "CARD_CLICKED",
                    "user": {"name": "users/1"},
                    "space": {"name": "spaces/A"},
                    "message": {"sender": {"type": "BOT"}},
                    "common": {"invokedFunction": action_name},
                }
            ),
        )

    level1 = await dispatcher.feed_update(click("menu.root"))
    level2 = await dispatcher.feed_update(click("menu.tickets"))
    back = await dispatcher.feed_update(click("menu.root"))
    for card in (level1, level2, back):
        print(cast(Card, card).to_dict()["header"]["title"])


if __name__ == "__main__":
    asyncio.run(main())
