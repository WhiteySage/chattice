"""Dialog bot: REQUEST_DIALOG -> Dialog -> SUBMIT_DIALOG -> ActionStatus.

Runs the full dialog lifecycle the Chat UI performs on its own: the
OPEN_DIALOG button fires REQUEST_DIALOG, the app answers with a `Dialog`
body, and the later SUBMIT_DIALOG carries the entered form inputs which the
`dialog_submit` handler turns into an ActionStatus (mirroring
tests/cards/test_gate_dialog.py).

Run:
    uv run python examples/bots/dialog_bot.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import ActionStatus, Card, Dialog, Section, TextInput
from chattice.events import ActionEvent, StringInput


async def main() -> None:
    router = Router()

    @router.action("open.contact")
    async def open_dialog(event: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(sections=[Section(widgets=[TextInput(name="name", label="Имя")])])
        )

    @router.dialog_submit()
    async def submit(event: ActionEvent) -> ActionStatus:
        name = event.form_inputs["name"]
        assert isinstance(name, StringInput)
        return ActionStatus.ok(f"Saved {name.values[0]!r}")

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
    print("dialog json:", dialog.to_dict())

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
    assert status == ActionStatus.ok("Saved 'Иван'")
    print("dialog status:", status.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
