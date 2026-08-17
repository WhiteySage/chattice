"""Form bot: Card with TextInput + Validation -> SUBMIT_DIALOG -> ActionStatus.

Shows the full form contract: the input declares client-side validation
(character limit and email type), the documented SUBMIT_DIALOG payload carries
`common.formInputs`, and `@router.dialog_submit()` reads them back and answers
with an ActionStatus the Chat UI renders as a confirmation banner.

Run:
    python examples/bots/form_bot.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Card,
    Section,
    TextInput,
    TextInputType,
    Validation,
)
from chattice.events import ActionEvent, StringInput


async def main() -> None:
    card = Card(
        sections=[
            Section(
                widgets=[
                    TextInput(
                        name="email",
                        label="Email",
                        validation=Validation(
                            character_limit=100, input_type=TextInputType.EMAIL
                        ),
                    )
                ]
            )
        ]
    )
    print("card json:", card.to_dict())

    router = Router()

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> ActionStatus:
        email = event.form_inputs["email"]
        assert isinstance(email, StringInput)
        return ActionStatus.ok(f"Saved {email.values[0]!r}")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    # The documented SUBMIT_DIALOG payload with formInputs (as in
    # tests/fixtures/google_chat/interactions/card_clicked_submit_dialog.json).
    status = await dispatcher.feed_update(
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "isDialogEvent": True,
                "dialogEventType": "SUBMIT_DIALOG",
                "common": {
                    "invokedFunction": "contact.submit",
                    "formInputs": {"email": {"stringInputs": {"value": ["a@b.c"]}}},
                },
            }
        )
    )
    assert isinstance(status, ActionStatus)
    print("dialog status:", status.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
