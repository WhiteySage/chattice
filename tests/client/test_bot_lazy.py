"""Bot construction, lazy client, raw_client escape hatch."""

from __future__ import annotations

from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot, ChatAPIError, MessageReplyOption

from ._fake_transport import FakeChatTransport


async def test_bot_without_credentials_raises_on_first_call() -> None:
    bot = Bot()
    try:
        await bot.get_message("spaces/A/messages/1")
    except ChatAPIError as error:
        assert "credentials" in str(error).lower()
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError")


async def test_raw_client_without_credentials_raises() -> None:
    bot = Bot()
    try:
        _ = bot.raw_client  # B018: bare expression is useless; assign instead
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError")


async def test_client_is_created_once() -> None:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    bot = Bot(credentials=creds, transport=FakeChatTransport(credentials=creds))
    client = bot.raw_client
    assert bot.raw_client is client


def test_reply_option_mapping() -> None:
    from google.apps.chat_v1.types.message import (
        CreateMessageRequest as CreateMessageRequestProto,
    )

    ProtoReplyOption = CreateMessageRequestProto.MessageReplyOption

    assert (
        MessageReplyOption.REPLY_FALLBACK_TO_NEW_THREAD.to_proto()
        is ProtoReplyOption.REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD
    )
    assert (
        MessageReplyOption.REPLY_OR_FAIL.to_proto()
        is ProtoReplyOption.REPLY_MESSAGE_OR_FAIL
    )
    assert (
        MessageReplyOption.NEW_THREAD.to_proto()
        is ProtoReplyOption.MESSAGE_REPLY_OPTION_UNSPECIFIED
    )
