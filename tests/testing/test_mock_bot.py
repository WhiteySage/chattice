"""MockBot recorder contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chattice.testing import MockBot


async def test_send_recorded_with_arguments() -> None:
    bot = MockBot()
    sent = await bot.app.messages.create("spaces/AAA", text="hello")
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
    await bot.app.messages.create("spaces/AAA", text="pong")
    bot.assert_message_sent("pong")


async def test_assert_message_sent_fails_with_message() -> None:
    bot = MockBot()
    await bot.app.messages.create("spaces/AAA", text="other")
    with pytest.raises(AssertionError, match="pong"):
        bot.assert_message_sent("pong")


async def test_assert_no_messages() -> None:
    bot = MockBot()
    bot.assert_no_messages()
    await bot.app.messages.create("spaces/AAA", text="x")
    with pytest.raises(AssertionError):
        bot.assert_no_messages()


async def test_update_and_delete_recorded() -> None:
    bot = MockBot()
    await bot.app.messages.update("spaces/AAA/messages/1", text="new")
    await bot.app.messages.delete("spaces/AAA/messages/1")
    assert (
        "update_message",
        {"name": "spaces/AAA/messages/1", "text": "new", "card": None},
    ) in bot.calls
    assert ("delete_message", {"name": "spaces/AAA/messages/1"}) in bot.calls


async def test_get_fabricates_protos() -> None:
    bot = MockBot()
    message = await bot.app.messages.get("spaces/AAA/messages/1")
    assert message.name == "spaces/AAA/messages/1"
    space = await bot.app.spaces.get("spaces/AAA")
    assert space.name == "spaces/AAA"


async def test_assert_updated() -> None:
    bot = MockBot()
    await bot.app.messages.update("spaces/AAA/messages/1", text="new")
    bot.assert_updated("spaces/AAA/messages/1", "new")
    with pytest.raises(AssertionError, match="update_message"):
        bot.assert_updated("spaces/AAA/messages/1", "other")


async def test_user_identity_facade_shares_recorder() -> None:
    bot = MockBot()
    sent = await bot.user.messages.create("spaces/AAA", text="from user")
    assert sent.name == "spaces/AAA/messages/1"
    bot.assert_message_sent("from user")


async def test_upload_attachment_recorded() -> None:
    bot = MockBot()
    uploaded = await bot.upload_attachment(
        "spaces/AAA", SimpleNamespace(filename="report.png")
    )
    assert uploaded.filename == "report.png"
    assert uploaded.attachment_data_ref["resourceName"] == (
        "spaces/AAA/attachments/upload/1"
    )
    assert bot.calls[-1] == (
        "upload_attachment",
        {"space": "spaces/AAA", "filename": "report.png"},
    )


async def test_download_attachment_without_destination_returns_bytes() -> None:
    bot = MockBot()
    data = await bot.download_attachment(
        SimpleNamespace(resource_name="spaces/AAA/attachments/X")
    )
    assert data == b""


async def test_download_attachment_str_fallback_and_file_destination(
    tmp_path: Path,
) -> None:
    bot = MockBot()
    # No resource_name attribute → str(attachment) fallback.
    assert await bot.download_attachment("spaces/AAA/attachments/RAW") == b""

    destination = tmp_path / "out.bin"
    result = await bot.download_attachment(
        SimpleNamespace(resource_name="spaces/AAA/attachments/X"),
        destination=destination,
    )
    assert result == destination
    assert destination.exists() and destination.read_bytes() == b""
    assert [kind for kind, _ in bot.calls] == ["download_attachment"] * 2


async def test_get_attachment_records_and_fabricates_ref() -> None:
    bot = MockBot()
    ref = await bot.get_attachment("spaces/AAA/attachments/Y")
    assert ref.name == "spaces/AAA/attachments/Y"
    assert bot.calls[-1] == ("get_attachment", {"name": "spaces/AAA/attachments/Y"})


async def test_assert_message_sent_count_mismatch_fails() -> None:
    bot = MockBot()
    await bot.app.messages.create("spaces/AAA", text="hello")
    with pytest.raises(AssertionError, match="expected 2 sent"):
        bot.assert_message_sent(count=2)
