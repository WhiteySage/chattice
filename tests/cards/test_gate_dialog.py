"""Gate: Card with form+OPEN_DIALOG button -> REQUEST_DIALOG -> Dialog ->
SUBMIT_DIALOG with formInputs -> dialog_submit -> ActionStatus.ok."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Button,
    ButtonInteraction,
    ButtonList,
    Card,
    CardHeader,
    Dialog,
    Section,
    TextInput,
    TextParagraph,
)
from chattice.events import ActionEvent


async def test_dialog_cycle_without_raw_json() -> None:
    card = Card(
        header=CardHeader(title="Contact"),
        sections=[
            Section(
                widgets=[
                    TextParagraph("Add a contact"),
                    TextInput(name="name", label="Имя"),
                    ButtonList(
                        buttons=[
                            Button(
                                "Open form",
                                action="open.contact",
                                interaction=ButtonInteraction.OPEN_DIALOG,
                            )
                        ]
                    ),
                ]
            )
        ],
    )
    serialized = card.to_dict()
    assert (
        serialized["sections"][0]["widgets"][2]["buttonList"]["buttons"][0]["onClick"][
            "action"
        ]["interaction"]
        == "OPEN_DIALOG"
    )

    router = Router()

    @router.action("open.contact")
    async def open_dialog(action: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(sections=[Section(widgets=[TextInput(name="name", label="Имя")])])
        )

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> ActionStatus:
        assert "name" in event.form_inputs
        return ActionStatus.ok("Saved")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    request_payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "isDialogEvent": True,
        "dialogEventType": "REQUEST_DIALOG",
        "common": {
            "invokedFunction": "open.contact",
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }
    dialog = await dispatcher.feed_update(parse_interaction(request_payload))
    assert isinstance(dialog, Dialog)
    assert (
        dialog.to_dict()["dialog"]["body"]["sections"][0]["widgets"][0]["textInput"][
            "name"
        ]
        == "name"
    )

    submit_payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "common": {
            "invokedFunction": "open.contact",
            "formInputs": {"name": {"stringInputs": {"value": ["Иван"]}}},
            "userLocale": "en-US",
            "timeZone": {"id": "America/Los_Angeles", "offset": -25200000},
        },
    }
    status = await dispatcher.feed_update(parse_interaction(submit_payload))
    assert status == ActionStatus.ok("Saved")
