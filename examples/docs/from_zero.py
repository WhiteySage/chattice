"""The documented end-to-end example, executable without Google credentials.

This intentionally uses only public Chattice imports. Google Console setup is a
human step; every framework-side operation is exercised for real through the
parser, dispatchers, typed cards/forms/dialogs, and the public testing toolkit.

Run from a checkout:
    python examples/docs/from_zero.py

The documentation audit also copies this file outside the checkout and runs it
with a clean virtual environment containing only the built wheel.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass

from chattice import Dispatcher, F, Router
from chattice.actions import ActionData
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import (
    ActionStatus,
    Button,
    ButtonInteraction,
    ButtonList,
    Card,
    Dialog,
    Section,
    TextInput,
    TextParagraph,
)
from chattice.events import ActionEvent, CommandEvent, MessageEvent, StringInput
from chattice.forms import FormModel
from chattice.testing import MockBot
from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    WorkspaceEventType,
    parse_workspace_event,
)


@dataclass
class ContactForm(FormModel):
    """Typed view of ``common.formInputs`` used by the dialog submit."""

    email: StringInput


@dataclass
class DeployAction(ActionData, function="deploy.confirm"):
    """Typed, application-owned parameters for the deploy button."""

    env: str


EventsNextHandler = Callable[
    [WorkspaceEvent, MutableMapping[str, object]], Awaitable[object]
]


def message_payload(text: str) -> dict[str, object]:
    """Build a documented MESSAGE interaction with a concrete thread."""
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-16T12:00:00Z",
        "user": {"name": "users/alice"},
        "space": {"name": "spaces/AAA"},
        "message": {
            "name": "spaces/AAA/messages/1",
            "text": text,
            "sender": {"name": "users/alice", "type": "HUMAN"},
            "thread": {"name": "spaces/AAA/threads/T1"},
        },
    }


async def run_interactions() -> None:
    bot = MockBot()
    router = Router(name="docs")

    @router.message(F.text == "hello")
    async def hello(message: MessageEvent) -> str:
        display_name = message.actor.display_name if message.actor is not None else None
        return f"Hello, {display_name or 'developer'}!"

    @router.message(F.text == "reply")
    async def reply(message: MessageEvent) -> str:
        await message.reply("contextual reply")
        return "replied"

    @router.message(F.text == "thread")
    async def continue_thread(message: MessageEvent) -> str:
        assert message.thread is not None
        await message.thread.send("explicit thread continuation")
        return "continued"

    @router.message(F.text == "top-level")
    async def top_level(message: MessageEvent) -> str:
        assert message.space is not None
        await message.space.send("new top-level message")
        return "sent"

    @router.message(F.text == "private")
    async def private(message: MessageEvent) -> str:
        assert message.space is not None
        assert message.actor is not None
        await bot.send_message(
            message.space,
            text="only Alice can see this",
            private_to=message.actor,
        )
        return "sent privately"

    @router.slash_command(F.command_id == 42)
    async def native_command(event: CommandEvent) -> str:
        return f"command 42: {event.message_text}"

    @router.action("deploy.confirm", DeployAction.filter())
    async def button_action(event: ActionEvent, data: DeployAction) -> str:
        return f"deploying {data.env}"

    @router.action("contact.open")
    async def open_dialog(event: ActionEvent) -> Dialog:
        return Dialog(
            body=Card(
                sections=[Section(widgets=[TextInput(name="email", label="Email")])]
            )
        )

    @router.dialog_submit(ContactForm.filter())
    async def submit_form(event: ActionEvent, form: ContactForm) -> ActionStatus:
        return ActionStatus.ok(f"Saved {form.email.values[0]}")

    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)

    hello_result = await dispatcher.feed_update(
        parse_interaction(message_payload("hello"))
    )
    assert hello_result == "Hello, developer!"

    assert (
        await dispatcher.feed_update(parse_interaction(message_payload("reply")))
        == "replied"
    )
    assert (
        await dispatcher.feed_update(parse_interaction(message_payload("thread")))
        == "continued"
    )
    assert (
        await dispatcher.feed_update(parse_interaction(message_payload("top-level")))
        == "sent"
    )
    assert (
        await dispatcher.feed_update(parse_interaction(message_payload("private")))
        == "sent privately"
    )

    command_result = await dispatcher.feed_update(
        parse_interaction(
            {
                "type": "MESSAGE",
                "user": {"name": "users/alice"},
                "space": {"name": "spaces/AAA"},
                "message": {
                    "name": "spaces/AAA/messages/2",
                    "text": "/deploy prod",
                    "argumentText": "prod",
                    "slashCommand": {"commandId": "42"},
                },
            }
        )
    )
    assert command_result == "command 42: prod"

    card = Card(
        sections=[
            Section(
                widgets=[
                    TextParagraph("Deploy production?"),
                    ButtonList(
                        buttons=[
                            Button(
                                "Deploy",
                                action=DeployAction(env="prod"),
                            ),
                            Button(
                                "Contact",
                                action="contact.open",
                                interaction=ButtonInteraction.OPEN_DIALOG,
                            ),
                        ]
                    ),
                ]
            )
        ]
    )
    serialized_card = card.to_dict()
    assert serialized_card["sections"][0]["widgets"][1]["buttonList"]

    action_result = await dispatcher.feed_update(
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "user": {"name": "users/alice"},
                "space": {"name": "spaces/AAA"},
                "common": {
                    "invokedFunction": "deploy.confirm",
                    "parameters": {"env": "prod"},
                },
            }
        )
    )
    assert action_result == "deploying prod"

    dialog_result = await dispatcher.feed_update(
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "user": {"name": "users/alice"},
                "space": {"name": "spaces/AAA"},
                "isDialogEvent": True,
                "dialogEventType": "REQUEST_DIALOG",
                "common": {"invokedFunction": "contact.open"},
            }
        )
    )
    assert isinstance(dialog_result, Dialog)

    form_result = await dispatcher.feed_update(
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "user": {"name": "users/alice"},
                "space": {"name": "spaces/AAA"},
                "isDialogEvent": True,
                "dialogEventType": "SUBMIT_DIALOG",
                "common": {
                    "invokedFunction": "contact.submit",
                    "formInputs": {
                        "email": {"stringInputs": {"value": ["alice@example.com"]}}
                    },
                },
            }
        )
    )
    assert form_result == ActionStatus.ok("Saved alice@example.com")

    sent_text = [call[1]["text"] for call in bot.calls if call[0] == "send_message"]
    assert sent_text == [
        "contextual reply",
        "explicit thread continuation",
        "new top-level message",
        "only Alice can see this",
    ]


async def run_workspace_event() -> None:
    root = EventsRouter(name="docs-events")
    messages = EventsRouter(name="docs-message-events")
    root.include_router(messages)

    @root.middleware
    async def add_audit_context(
        next_handler: EventsNextHandler,
        event: WorkspaceEvent,
        context: MutableMapping[str, object],
    ) -> object:
        context["source_label"] = "workspace"
        return await next_handler(event, context)

    async def add_event_kind(
        event: WorkspaceEvent, context: Mapping[str, object]
    ) -> Mapping[str, object]:
        return {"event_kind": event.cloud_type.rsplit(".", 1)[-1]}

    @messages.workspace_event(WorkspaceEventType.MESSAGE_CREATED, add_event_kind)
    async def created(event: WorkspaceEvent, source_label: str, event_kind: str) -> str:
        return f"{source_label} {event_kind} {event.subject}"

    dispatcher = EventsDispatcher()
    dispatcher.include_router(root)
    result = await dispatcher.feed_event(
        parse_workspace_event(
            {
                "specversion": "1.0",
                "id": "evt-docs-1",
                "source": "//chat.googleapis.com/spaces/AAA",
                "type": WorkspaceEventType.MESSAGE_CREATED,
                "subject": "spaces/AAA/messages/3",
                "time": "2026-08-16T12:00:00Z",
                "data": {},
            }
        )
    )
    assert result == "workspace created spaces/AAA/messages/3"


async def main() -> None:
    await run_interactions()
    await run_workspace_event()
    print("documentation journey OK")


if __name__ == "__main__":
    asyncio.run(main())
