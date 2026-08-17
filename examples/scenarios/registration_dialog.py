"""Registration (Dialog version): one Google-native interaction.

The same flow as registration_fsm.py but Google-native: a single dialog
collects ALL fields (name, email, department) in one interaction, the
submit handler answers with an ActionStatus banner. Forms
collect data — no FSM state needed for a one-shot collection.

Run:
    python examples/scenarios/registration_dialog.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Card,
    Dialog,
    Section,
    SelectionInput,
    TextInput,
)
from chattice.events import ActionEvent, StringInput
from chattice.forms import FormModel


@dataclass
class RegistrationForm(FormModel):
    name: StringInput
    email: StringInput
    department: StringInput


async def main() -> None:
    router = Router()

    @router.action("registration.open")
    async def open_dialog(event: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(
                sections=[
                    Section(
                        widgets=[
                            TextInput(name="name", label="Имя"),
                            TextInput(name="email", label="Email"),
                            SelectionInput(
                                name="department",
                                label="Отдел",
                                items=(
                                    {"text": "Sales", "value": "sales"},
                                    {"text": "Support", "value": "support"},
                                ),
                            ),
                        ]
                    )
                ]
            )
        )

    @router.dialog_submit(RegistrationForm.filter())
    async def submit(event: ActionEvent, form: RegistrationForm) -> ActionStatus:
        return ActionStatus.ok(
            f"Сохранено: {form.name.values[0]} <{form.email.values[0]}> "
            f"в {form.department.values[0]}"
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    # the UI flow: OPEN_DIALOG -> Dialog -> SUBMIT_DIALOG with typed inputs
    request = parse_interaction(
        {
            "type": "CARD_CLICKED",
            "isDialogEvent": True,
            "dialogEventType": "REQUEST_DIALOG",
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
            "common": {"invokedFunction": "registration.open"},
        }
    )
    dialog = await dispatcher.feed_update(request)
    assert isinstance(dialog, Dialog)
    print(
        "dialog widgets:", [type(w).__name__ for w in dialog.body.sections[0].widgets]
    )

    submit_payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {
            "invokedFunction": "registration.open",
            "formInputs": {
                "name": {"stringInputs": {"value": ["Иван"]}},
                "email": {"stringInputs": {"value": ["ivan@example.com"]}},
                "department": {"stringInputs": {"value": ["sales"]}},
            },
        },
    }
    status = await dispatcher.feed_update(parse_interaction(submit_payload))
    assert isinstance(status, ActionStatus)
    print("status:", status.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
