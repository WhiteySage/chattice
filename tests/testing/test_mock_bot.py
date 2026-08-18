"""MockBot recorder contract."""

from __future__ import annotations

import pytest

from chattice.testing import MockBot


async def test_send_recorded_with_arguments() -> None:
    bot = MockBot()
    sent = await bot.send_message("spaces/AAA", text="hello")
    assert sent.text == "hello"
    assert sent.name == "spaces/AAA/messages/1"
    assert bot.calls == [
        (
            "send_message",
            {
                "space": "spaces/AAA",
                "text": "hello",
                "card": None,
                "notify": None,
                "private_to": None,
                "attachments": None,
            },
        )
    ]


async def test_assert_message_sent_matches_text_and_count() -> None:
    bot = MockBot()
    await bot.send_message("spaces/AAA", text="pong")
    bot.assert_message_sent("pong")


async def test_assert_message_sent_fails_with_message() -> None:
    bot = MockBot()
    await bot.send_message("spaces/AAA", text="other")
    with pytest.raises(AssertionError, match="pong"):
        bot.assert_message_sent("pong")


async def test_assert_no_messages() -> None:
    bot = MockBot()
    bot.assert_no_messages()
    await bot.send_message("spaces/AAA", text="x")
    with pytest.raises(AssertionError):
        bot.assert_no_messages()


async def test_update_and_delete_recorded() -> None:
    bot = MockBot()
    await bot.update_message("spaces/AAA/messages/1", text="new")
    await bot.delete_message("spaces/AAA/messages/1")
    assert (
        "update_message",
        {"name": "spaces/AAA/messages/1", "text": "new", "card": None},
    ) in bot.calls
    assert ("delete_message", {"name": "spaces/AAA/messages/1"}) in bot.calls


async def test_get_fabricates_protos() -> None:
    bot = MockBot()
    message = await bot.get_message("spaces/AAA/messages/1")
    assert message.name == "spaces/AAA/messages/1"
    space = await bot.get_space("spaces/AAA")
    assert space.name == "spaces/AAA"


async def test_assert_updated() -> None:
    bot = MockBot()
    await bot.update_message("spaces/AAA/messages/1", text="new")
    bot.assert_updated("spaces/AAA/messages/1", "new")
    with pytest.raises(AssertionError, match="update_message"):
        bot.assert_updated("spaces/AAA/messages/1", "other")
