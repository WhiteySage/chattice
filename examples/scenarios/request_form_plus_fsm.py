"""Request form + FSM: the form collects; FSM REMEMBERS durable state.

A Google-native form collects all fields in one
interaction, and an FSM record stores the durable workflow state that
must survive restarts, external callbacks, and later approval steps.
The approval step advances the FSM record with compare-and-set.

Run:
    python examples/scenarios/request_form_plus_fsm.py
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
    SelectionInput,
    TextInput,
    TextParagraph,
)
from chattice.events import ActionEvent, StringInput
from chattice.forms import FormModel
from chattice.fsm import FSMRecord, MemoryFSMRecordStorage, StorageKey
from chattice.fsm.states import State, StatesGroup


class RequestFlow(StatesGroup):
    pending_approval = State()
    done = State()


@dataclass
class RequestForm(FormModel):
    category: StringInput
    priority: StringInput
    details: StringInput


async def main() -> None:
    storage = MemoryFSMRecordStorage()
    key = StorageKey(user="users/1", space="spaces/A", thread=None)
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
                                items=({"text": "IT", "value": "it"},),
                            ),
                            SelectionInput(
                                name="priority",
                                label="Приоритет",
                                items=({"text": "Высокий", "value": "high"},),
                            ),
                            TextInput(name="details", label="Описание"),
                        ]
                    )
                ]
            )
        )

    @router.dialog_submit(RequestForm.filter())
    async def submit(event: ActionEvent, form: RequestForm) -> ActionStatus:
        # Durable state: survives restarts and external callbacks.
        await storage.compare_and_set(
            key,
            expected_revision=0,
            replacement=FSMRecord(
                state=RequestFlow.pending_approval.state,
                data={
                    "category": form.category.values[0],
                    "priority": form.priority.values[0],
                    "details": form.details.values[0],
                },
                expires_at=None,  # no expiry: durable until approved
            ),
        )
        return ActionStatus.ok("Заявка создана и ждёт утверждения")

    @router.action("request.approve")
    async def approve(event: ActionEvent) -> Card:
        record = await storage.get_record(key)
        assert record is not None
        await storage.compare_and_set(
            key,
            expected_revision=record.revision,
            replacement=FSMRecord(state=RequestFlow.done.state, data=record.data),
        )
        # a card click answers with an UPDATED card (bot message), never
        # ActionStatus — that response is dialog-submit only.
        return Card(
            header=CardHeader(title="Заявка утверждена"),
            sections=[Section(widgets=[TextParagraph(str(dict(record.data)))])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    def submit_payload() -> dict[str, object]:
        return {
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
                    "details": {"stringInputs": {"value": ["Принтер"]}},
                },
            },
        }

    print(
        "submit:",
        cast(
            ActionStatus,
            await dispatcher.feed_update(parse_interaction(submit_payload())),
        ).to_dict(),
    )
    record = await storage.get_record(key)
    assert record is not None
    print("durable record:", record.state, dict(record.data))
    approve_payload = {
        "type": "CARD_CLICKED",
        "user": {"name": "users/2"},
        "space": {"name": "spaces/A"},
        "message": {"sender": {"type": "BOT"}},
        "common": {"invokedFunction": "request.approve"},
    }
    print(
        "approve:",
        cast(
            ActionStatus,
            await dispatcher.feed_update(parse_interaction(approve_payload)),
        ).to_dict(),
    )
    record = await storage.get_record(key)
    assert record is not None
    print("final state:", record.state)


if __name__ == "__main__":
    asyncio.run(main())
