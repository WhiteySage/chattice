"""Private dialog -> public card: private collection, public posting.

The user fills a PRIVATE dialog (visible only to them); the handler then
posts a PUBLIC card into the space through the outgoing Bot. The recipe
demonstrates the pattern with the testing MockBot standing in for the
real client (production: Bot with app credentials).

Run:
    python examples/scenarios/private_dialog_to_public_card.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Card,
    CardHeader,
    Dialog,
    Section,
    TextInput,
    TextParagraph,
)
from chattice.events import ActionEvent, StringInput
from chattice.forms import FormModel
from chattice.testing import MockBot


@dataclass
class AnnouncementForm(FormModel):
    title: StringInput
    body: StringInput


async def main() -> None:
    router = Router()

    @router.action("announce.open")
    async def open_dialog(event: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(
                sections=[
                    Section(
                        widgets=[
                            TextInput(name="title", label="Заголовок"),
                            TextInput(name="body", label="Текст"),
                        ]
                    )
                ]
            )
        )

    @router.dialog_submit(AnnouncementForm.filter())
    async def publish(
        event: ActionEvent, form: AnnouncementForm, bot: MockBot
    ) -> ActionStatus:
        # PRIVATE collection above; PUBLIC card below — an authenticated
        # outgoing call, not a synchronous response.
        card = Card(
            header=CardHeader(title=form.title.values[0]),
            sections=[Section(widgets=[TextParagraph(form.body.values[0])])],
        )
        await bot.send_message(event.space, text="", card=card)
        return ActionStatus.ok("Опубликовано в пространстве")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    bot = MockBot()

    open_payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "REQUEST_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {"invokedFunction": "announce.open"},
    }
    dialog = await dispatcher.feed_update(parse_interaction(open_payload))
    assert isinstance(dialog, Dialog)
    print("private dialog opened")

    submit_payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {
            "invokedFunction": "announce.open",
            "formInputs": {
                "title": {"stringInputs": {"value": ["Релиз 2.0"]}},
                "body": {"stringInputs": {"value": ["Доступен в проде"]}},
            },
        },
    }
    status = await dispatcher.feed_update(parse_interaction(submit_payload), bot=bot)
    print("status:", cast(ActionStatus, status).to_dict())
    print("public card posted:", [c for c, _ in bot.calls])


if __name__ == "__main__":
    asyncio.run(main())
