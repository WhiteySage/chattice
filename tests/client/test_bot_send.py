"""send_message request contract."""

from __future__ import annotations

from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot, ChatAPIError, MessageReplyOption
from chattice.events import SpaceRef, ThreadRef

from ._fake_transport import FakeChatTransport


def _bot(transport: FakeChatTransport) -> Bot:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    return Bot(credentials=creds, transport=transport)


async def test_send_message_builds_minimal_request() -> None:
    transport = FakeChatTransport()
    message = await _bot(transport).send_message("spaces/AAA", text="hello")
    request = transport.requests[-1]
    assert request.parent == "spaces/AAA"
    assert request.message.text == "hello"
    assert message.text == "hello"
    assert message.name.startswith("spaces/AAA/messages/")


async def test_send_message_accepts_space_ref() -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message(SpaceRef(name="spaces/BBB"), text="hi")
    assert transport.requests[-1].parent == "spaces/BBB"


async def test_send_message_targets_thread() -> None:
    transport = FakeChatTransport()
    thread = ThreadRef(name="spaces/AAA/threads/t1")
    await _bot(transport).send_message("spaces/AAA", text="in thread", thread=thread)
    request = transport.requests[-1]
    assert request.message.thread.name == "spaces/AAA/threads/t1"


async def test_send_message_creates_thread_by_key() -> None:
    """Live dogfooding regression: an app-defined threadKey must reach the
    wire (it was silently dropped — the thread never got created)."""
    transport = FakeChatTransport()
    thread = ThreadRef(thread_key="menu.users-1")
    await _bot(transport).send_message("spaces/AAA", text="menu", thread=thread)
    request = transport.requests[-1]
    assert request.message.thread.thread_key == "menu.users-1"


async def test_send_message_reply_or_fail_option() -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message(
        "spaces/AAA",
        text="strict reply",
        thread=ThreadRef(name="spaces/AAA/threads/t1"),
        reply_option=MessageReplyOption.REPLY_OR_FAIL,
    )
    from google.apps.chat_v1.types.message import (
        CreateMessageRequest as CreateMessageRequestProto,
    )

    reply_option = CreateMessageRequestProto.MessageReplyOption
    assert (
        transport.requests[-1].message_reply_option
        is reply_option.REPLY_MESSAGE_OR_FAIL
    )


async def test_send_message_without_thread_uses_new_thread_option() -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message("spaces/AAA", text="top level")
    from google.apps.chat_v1.types.message import (
        CreateMessageRequest as CreateMessageRequestProto,
    )

    reply_option = CreateMessageRequestProto.MessageReplyOption
    assert (
        transport.requests[-1].message_reply_option
        is reply_option.MESSAGE_REPLY_OPTION_UNSPECIFIED
    )


async def test_send_message_passes_request_id_and_message_id() -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message(
        "spaces/AAA", text="idempotent", request_id="req-1", message_id="client-x"
    )
    request = transport.requests[-1]
    assert request.request_id == "req-1"
    assert request.message_id == "client-x"


async def test_send_message_with_unnamed_space_ref_raises() -> None:
    try:
        await _bot(FakeChatTransport()).send_message(SpaceRef(name=None), text="x")
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError")


async def test_send_message_with_card() -> None:
    """Dogfooding finding (Phase 15): Bot sends cards natively."""
    from google.auth.credentials import AnonymousCredentials

    from chattice.cards import Card, CardHeader, Section, TextParagraph
    from chattice.client import Bot

    from ._fake_transport import FakeChatTransport

    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(credentials=creds)
    bot = Bot(credentials=creds, transport=transport)
    card = Card(
        header=CardHeader(title="T"),
        sections=[Section(widgets=[TextParagraph("hi")])],
    )
    await bot.send_message("spaces/AAA", text="", card=card)
    request = transport.requests[-1]
    assert len(request.message.cards_v2) == 1
    assert request.message.cards_v2[0].card.header.title == "T"
