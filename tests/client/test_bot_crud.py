"""get/update/delete message and get_space contracts."""

from __future__ import annotations

from google.apps.chat_v1.types.space import Space
from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot, ChatNotFoundError

from ._fake_transport import FakeChatTransport


def _bot(transport: FakeChatTransport) -> Bot:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    return Bot(credentials=creds, transport=transport)


async def test_get_message_round_trip() -> None:
    transport = FakeChatTransport()
    sent = await _bot(transport).send_message("spaces/AAA", text="stored")
    fetched = await _bot(transport).get_message(sent.name)
    assert fetched.name == sent.name
    assert fetched.text == "stored"


async def test_get_missing_message_raises_not_found() -> None:
    try:
        await _bot(FakeChatTransport()).get_message("spaces/AAA/messages/nope")
    except ChatNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatNotFoundError")


async def test_update_message_changes_text() -> None:
    transport = FakeChatTransport()
    sent = await _bot(transport).send_message("spaces/AAA", text="before")
    updated = await _bot(transport).update_message(sent.name, text="after")
    assert updated.name == sent.name
    assert updated.text == "after"
    fetched = await _bot(transport).get_message(sent.name)
    assert fetched.text == "after"


async def test_update_missing_message_raises_not_found() -> None:
    try:
        await _bot(FakeChatTransport()).update_message(
            "spaces/AAA/messages/nope", text="x"
        )
    except ChatNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatNotFoundError")


async def test_update_message_card_uses_proto_field_mask() -> None:
    """Live dogfooding regression: the gRPC update mask uses the PROTO
    field name cards_v2 — "cardsV2" (the REST JSON spelling) is rejected
    by the API with "Unsupported path name in message field mask"."""
    from chattice.cards import Card, CardHeader

    transport = FakeChatTransport()
    sent = await _bot(transport).send_message(
        "spaces/AAA", card=Card(header=CardHeader(title="v1"))
    )
    await _bot(transport).update_message(
        sent.name, card=Card(header=CardHeader(title="v2"))
    )
    request = transport.updates[-1]
    assert list(request.update_mask.paths) == ["cards_v2"]


async def test_delete_message_removes_it() -> None:
    transport = FakeChatTransport()
    sent = await _bot(transport).send_message("spaces/AAA", text="doomed")
    await _bot(transport).delete_message(sent.name)
    try:
        await _bot(transport).get_message(sent.name)
    except ChatNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatNotFoundError after delete")


async def test_get_space_returns_stored_space() -> None:
    transport = FakeChatTransport()
    transport.spaces["spaces/AAA"] = Space(name="spaces/AAA", display_name="Demo")
    space = await _bot(transport).get_space("spaces/AAA")
    assert space.name == "spaces/AAA"
    assert space.display_name == "Demo"


async def test_get_missing_space_raises_not_found() -> None:
    try:
        await _bot(FakeChatTransport()).get_space("spaces/nope")
    except ChatNotFoundError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatNotFoundError")
