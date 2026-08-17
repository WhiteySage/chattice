"""Request form: one interaction collects the whole request (Google-native).

Forms collect data. A single dialog collects category,
priority and details at once; the submit handler hands the typed
RequestForm to the application. No FSM anywhere in this flow.

Run:
    python examples/scenarios/request_form.py
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
    Dialog,
    Section,
    SelectionInput,
    TextInput,
)
from chattice.events import ActionEvent, StringInput
from chattice.forms import FormModel


@dataclass
class RequestForm(FormModel):
    category: StringInput
    priority: StringInput
    details: StringInput


async def main() -> None:
    router = Router()

    @router.action("request.open")
    async def open_form(event: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(
                sections=[
                    Section(
                        widgets=[
                            SelectionInput(
                                name="category",
                                label="Категория",
                                items=(
                                    {"text": "IT", "value": "it"},
                                    {"text": "HR", "value": "hr"},
                                ),
                            ),
                            SelectionInput(
                                name="priority",
                                label="Приоритет",
                                items=(
                                    {"text": "Низкий", "value": "low"},
                                    {"text": "Высокий", "value": "high"},
                                ),
                            ),
                            TextInput(name="details", label="Описание"),
                        ]
                    )
                ]
            )
        )

    @router.dialog_submit(RequestForm.filter())
    async def submit(event: ActionEvent, form: RequestForm) -> ActionStatus:
        # hand the typed request to the application layer
        request = {
            "category": form.category.values[0],
            "priority": form.priority.values[0],
            "details": form.details.values[0],
        }
        return ActionStatus.ok(f"Заявка создана: {request}")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {
            "invokedFunction": "request.open",
            "formInputs": {
                "category": {"stringInputs": {"value": ["it"]}},
                "priority": {"stringInputs": {"value": ["high"]}},
                "details": {"stringInputs": {"value": ["Принтер не работает"]}},
            },
        },
    }
    status = await dispatcher.feed_update(parse_interaction(payload))
    print("status:", cast(ActionStatus, status).to_dict())


if __name__ == "__main__":
    asyncio.run(main())
