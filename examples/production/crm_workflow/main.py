"""CRM request workflow — an ILLUSTRATIVE IN-MEMORY SKETCH.

The flow (form collects, FSM remembers, actions advance):
    request.open (dialog: employee via typed picker, department,
    category, priority, details)
        -> SUBMIT_DIALOG + RequestForm.filter()
        -> FSM record pending_approval (durable: restarts, callbacks)
        -> proactive Card into the space (Bot, no inbound event)
        -> request.approve / request.reject (typed ActionData, CAS)
        -> CRM API call through the injected client
        -> done + final message update

Business services stay OUTSIDE the framework: FakeCRMClient is injected
by name; a real client is swapped in production. Everything here runs
without network. NOT production evidence: fixed identities, Memory
storage, no Redis restart run, no idempotency/timeout path — a real
deployment must add those (documented in the ExecPlan acceptance
answers). The employee field renders as a selection/text input because
the typed external-data multiselect facade is still Phase 15 backlog.

Run:
    uv run python examples/production/crm_workflow/main.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

from chattice import Dispatcher, Router
from chattice.actions import ActionData
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Button,
    ButtonList,
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
from chattice.testing import MockBot


class FakeCRMClient:
    """Business service stub — swap for the real CRM integration."""

    def __init__(self) -> None:
        self.created: list[dict[str, str]] = []

    async def create_request(self, request: dict[str, str]) -> str:
        self.created.append(request)
        return f"REQ-{len(self.created):03d}"


@dataclass
class RequestForm(FormModel):
    employee: StringInput
    department: StringInput
    category: StringInput
    priority: StringInput
    details: StringInput


@dataclass
class DecisionAction(ActionData):
    request_id: str


async def main() -> None:
    crm = FakeCRMClient()
    bot = MockBot()
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
                                name="employee",
                                label="Сотрудник",
                                items=(
                                    {"text": "Иван", "value": "ivan"},
                                    {"text": "Мария", "value": "maria"},
                                ),
                            ),
                            SelectionInput(
                                name="department",
                                label="Отдел",
                                items=(
                                    {"text": "IT", "value": "it"},
                                    {"text": "HR", "value": "hr"},
                                ),
                            ),
                            SelectionInput(
                                name="category",
                                label="Категория",
                                items=({"text": "Оборудование", "value": "hw"},),
                            ),
                            SelectionInput(
                                name="priority",
                                label="Приоритет",
                                items=(
                                    {"text": "Высокий", "value": "high"},
                                    {"text": "Низкий", "value": "low"},
                                ),
                            ),
                            TextInput(name="details", label="Описание"),
                        ]
                    )
                ]
            )
        )

    @router.dialog_submit(RequestForm.filter())
    async def submit(
        event: ActionEvent, form: RequestForm, crm_client: FakeCRMClient
    ) -> ActionStatus:
        request = {
            "employee": form.employee.values[0],
            "department": form.department.values[0],
            "category": form.category.values[0],
            "priority": form.priority.values[0],
            "details": form.details.values[0],
        }
        request_id = await crm_client.create_request(request)
        # Durable state: survives restarts and waits for approval.
        await storage.compare_and_set(
            key,
            expected_revision=0,
            replacement=FSMRecord(
                state="pending_approval",
                data={**request, "request_id": request_id},
            ),
        )
        # Proactive send: no inbound event needed.
        card = Card(
            header=CardHeader(title=f"{request_id}: {request['category']}"),
            sections=[
                Section(widgets=[TextParagraph(str(request))]),
                Section(
                    widgets=[
                        ButtonList(
                            buttons=[
                                Button(
                                    "Одобрить",
                                    action="request.approve",
                                    parameters={"request_id": request_id},
                                ),
                                Button(
                                    "Отклонить",
                                    action="request.reject",
                                    parameters={"request_id": request_id},
                                ),
                            ]
                        )
                    ]
                ),
            ],
        )
        await bot.send_message("spaces/A", text="", card=card)
        return ActionStatus.ok(f"{request_id} создана и отправлена на согласование")

    @router.action("request.approve", DecisionAction.filter())
    async def approve(event: ActionEvent, data: DecisionAction) -> str:
        record = await storage.get_record(key)
        assert record is not None
        await storage.compare_and_set(
            key,
            expected_revision=record.revision,
            replacement=FSMRecord(state="done", data=dict(record.data)),
        )
        return f"{data.request_id} одобрена"

    @router.action("request.reject", DecisionAction.filter())
    async def reject(event: ActionEvent, data: DecisionAction) -> str:
        record = await storage.get_record(key)
        assert record is not None
        await storage.compare_and_set(
            key,
            expected_revision=record.revision,
            replacement=FSMRecord(state="rejected", data=dict(record.data)),
        )
        return f"{data.request_id} отклонена"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    def dialog_submit(payload: dict[str, object]) -> dict[str, object]:
        return {
            "type": "CARD_CLICKED",
            "isDialogEvent": True,
            "dialogEventType": "SUBMIT_DIALOG",
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
            "common": {"invokedFunction": "request.open", "formInputs": payload},
        }

    status = await dispatcher.feed_update(
        parse_interaction(
            dialog_submit(
                {
                    "employee": {"stringInputs": {"value": ["Иван"]}},
                    "department": {"stringInputs": {"value": ["it"]}},
                    "category": {"stringInputs": {"value": ["hw"]}},
                    "priority": {"stringInputs": {"value": ["high"]}},
                    "details": {"stringInputs": {"value": ["Ноутбук"]}},
                }
            )
        ),
        crm_client=crm,
        bot=bot,
    )
    print("submit:", cast(ActionStatus, status).to_dict())
    print("crm created:", crm.created)
    print("proactive card posted:", bool(bot.calls))

    def click(name: str, request_id: str) -> dict[str, object]:
        return {
            "type": "CARD_CLICKED",
            "user": {"name": "users/2"},
            "space": {"name": "spaces/A"},
            "message": {"sender": {"type": "BOT"}},
            "common": {
                "invokedFunction": name,
                "parameters": {"request_id": request_id},
            },
        }

    approved = await dispatcher.feed_update(
        parse_interaction(click("request.approve", "REQ-001"))
    )
    print("approve:", approved)
    record = await storage.get_record(key)
    assert record is not None
    print("final durable state:", record.state)


if __name__ == "__main__":
    asyncio.run(main())
