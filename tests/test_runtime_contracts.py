"""Runtime contracts backed by representative Google payloads."""

from __future__ import annotations

from typing import cast

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice import Dispatcher, F, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.auth import AuthMode
from chattice.cards import Action, Button, Card, CardHeader, Section, SelectionInput
from chattice.client import Bot
from chattice.events import MessageEvent, UserRef
from tests.client._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _message(text: str, **message_fields: object) -> MessageEvent:
    payload: dict[str, object] = {
        "type": "MESSAGE",
        "message": {"text": text, **message_fields},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
    }
    return cast(MessageEvent, parse_interaction(payload))


async def test_argument_text_routes_mention_stripped() -> None:
    """`@MyApp ping` routes as `ping` via argument_text — no custom mention
    parser; raw text stays available."""
    router = Router()

    @router.message(F.argument_text.regexp(r"^[Pp]ing$"))
    async def ping(message: MessageEvent) -> str:
        assert message.text == "@MyApp ping"  # raw preserved
        return "pong"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    event = _message("@MyApp ping", argumentText=" ping ")
    assert await dispatcher.feed_update(event) == "pong"


async def test_argument_text_absent_for_ordinary_messages() -> None:
    event = _message("ping")
    assert event.argument_text is None
    assert event.text == "ping"


@pytest.mark.parametrize(
    ("argument_text", "expected"),
    [(" report", "report"), ("report  ", "report"), ("  report  ", "report"), ("", "")],
)
async def test_argument_text_normalization(argument_text: str, expected: str) -> None:
    event = _message("@MyApp report", argumentText=argument_text)
    assert event.argument_text == expected
    assert event.text == "@MyApp report"


async def test_argument_text_ignores_other_mentions() -> None:
    """Only the APP's mentions are stripped by Google; other-user mentions
    remain part of the documented argumentText."""
    event = _message("@MyApp hey @user", argumentText="hey @user")
    assert event.argument_text == "hey @user"


async def test_button_persist_and_load_indicator() -> None:
    button = Button(
        "Save", action="form.save", persist_values=True, load_indicator=True
    )
    action_proto = button.to_proto().on_click.action
    assert action_proto.persist_values is True
    assert action_proto.load_indicator.name == "SPINNER"


async def test_selection_input_external_data_source() -> None:
    selection = SelectionInput(
        name="employee",
        label="Employee",
        external_data_source=Action(function="employee.search"),
        multi_select_max_selected_items=5,
        multi_select_min_query_length=2,
    )
    proto = selection.to_proto()
    assert proto.external_data_source.function == "employee.search"
    assert proto.multi_select_max_selected_items == 5
    assert proto.multi_select_min_query_length == 2


async def test_bot_send_notify_and_private() -> None:
    creds = _creds()
    transport = FakeChatTransport(credentials=creds)
    # notify + private_to are app-auth surfaces, so the bot must be
    # explicit about the outgoing mode (fail-closed otherwise).
    bot = Bot(credentials=creds, transport=transport, auth_mode=AuthMode.APP)
    await bot.app.messages.create(
        "spaces/AAA",
        text="secret",
        notify="silent",
        private_to=UserRef(name="users/9"),
    )
    request = transport.requests[-1]
    message = request.message
    assert message.private_message_viewer.name == "users/9"
    options = request.create_message_notification_options
    assert options.notification_type.name == "NOTIFICATION_TYPE_SILENT"


async def test_bot_update_message_with_card() -> None:
    from google.apps.chat_v1.types.message import Message

    creds = _creds()
    transport = FakeChatTransport(credentials=creds)
    transport.messages["spaces/AAA/messages/1"] = Message(name="spaces/AAA/messages/1")
    bot = Bot(credentials=creds, transport=transport)
    card = Card(header=CardHeader(title="V2"), sections=[Section()])
    await bot.app.messages.update("spaces/AAA/messages/1", card=card)
    request = transport.updates[-1] if hasattr(transport, "updates") else None
    assert request is not None
    # The gRPC mask takes the proto field name cards_v2.
    # ("cardsV2" is rejected by the API).
    assert request.update_mask.paths == ["cards_v2"]
    assert request.message.cards_v2[0].card.header.title == "V2"
