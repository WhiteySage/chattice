"""Bot media API: upload/download/get + attachments in send_message."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from google.auth.credentials import AnonymousCredentials, Credentials

import chattice.media._rest  # noqa: F401 — imported for monkeypatching
from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.client import Bot, ChatAPIError
from chattice.events import SpaceRef
from chattice.media import (
    AttachmentRef,
    AttachmentSource,
    InputFile,
    UploadedAttachment,
)
from chattice.testing.fake_transport import FakeChatTransport


class _UserCreds(AnonymousCredentials):
    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_token = "user-token"
        self.scopes = ("https://www.googleapis.com/auth/chat.messages",)


class _AppCreds(AnonymousCredentials):
    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.signer = object()
        self.scopes = ("https://www.googleapis.com/auth/chat.bot",)


def _bot(
    credentials: Credentials | None, transport: FakeChatTransport | None = None
) -> Bot:
    return Bot(credentials=credentials, transport=transport)


async def test_upload_attachment_user_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_upload(
        credentials: Credentials,
        parent: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        timeout: float | None,
    ) -> dict[str, Any]:
        captured.update(
            parent=parent, filename=filename, content_type=content_type, data=data
        )
        return {"attachmentDataRef": {"resourceName": "media/r1"}}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    uploaded = await _bot(_UserCreds()).upload_attachment(
        "S1", InputFile.from_bytes(b"data", filename="r.png")
    )
    assert uploaded.space == "spaces/S1"
    assert uploaded.filename == "r.png"
    assert uploaded.attachment_data_ref["resourceName"] == "media/r1"
    assert captured["parent"] == "spaces/S1"
    assert captured["data"] == b"data"
    assert captured["content_type"] == "image/png"


async def test_upload_attachment_app_auth_rejected() -> None:
    with pytest.raises(CapabilityNotSupported, match="user authentication"):
        await _bot(_AppCreds()).upload_attachment(
            "S1", InputFile.from_bytes(b"x", filename="x.png")
        )


async def test_upload_attachment_dual_identity_uses_user_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Credentials] = []

    def fake_upload(
        credentials: Credentials,
        parent: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        timeout: float | None,
    ) -> dict[str, Any]:
        captured.append(credentials)
        return {"attachmentDataRef": {"resourceName": "media/r1"}}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    user_credentials = _UserCreds()
    app_credentials = _AppCreds()
    bot = Bot(
        app_credentials_provider=lambda: app_credentials,
        user_credentials_provider=lambda: user_credentials,
    )
    await bot.upload_attachment("S1", InputFile.from_bytes(b"x", filename="x.png"))
    assert captured[0] is user_credentials


async def test_upload_attachment_provider_returned_service_account_rejected() -> None:
    bot = Bot(
        app_credentials_provider=lambda: _AppCreds(),
        user_credentials_provider=lambda: _AppCreds(),
    )
    with pytest.raises(
        CapabilityNotSupported, match="DelegatedUserCredentialsProvider"
    ):
        await bot.upload_attachment("S1", InputFile.from_bytes(b"x", filename="x.png"))


async def test_upload_attachment_delegated_dwd_credentials_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Domain-wide delegation: with_subject keeps .signer but adds _subject,
    so the delegated service account must classify as USER, not APP."""
    captured: list[Credentials] = []

    def fake_upload(
        credentials: Credentials,
        parent: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        timeout: float | None,
    ) -> dict[str, Any]:
        captured.append(credentials)
        return {"attachmentDataRef": {"resourceName": "media/dwd"}}

    class DelegatedCreds(_AppCreds):
        def __init__(self) -> None:
            super().__init__()
            self._subject = "chat-bot-user@company.com"
            self.scopes = ("https://www.googleapis.com/auth/chat.messages",)

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    delegated = DelegatedCreds()
    bot = Bot(
        app_credentials_provider=lambda: _AppCreds(),
        user_credentials_provider=lambda: delegated,
    )
    uploaded = await bot.upload_attachment(
        "S1", InputFile.from_bytes(b"x", filename="x.png")
    )
    assert captured[0] is delegated
    assert uploaded.attachment_data_ref["resourceName"] == "media/dwd"


async def test_upload_attachment_user_without_scope_rejected() -> None:
    class NarrowUserCreds(_UserCreds):
        def __init__(self) -> None:
            super().__init__()
            self.scopes = ("https://www.googleapis.com/auth/other.only",)

    with pytest.raises(CapabilityNotSupported, match="ATTACHMENT_UPLOAD"):
        await _bot(NarrowUserCreds()).upload_attachment(
            "S1", InputFile.from_bytes(b"x", filename="x.png")
        )


async def test_upload_attachment_missing_media_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "googleapiclient", None)
    with pytest.raises(ChatAPIError, match=r"chattice\[media\]"):
        await _bot(_UserCreds()).upload_attachment(
            "S1", InputFile.from_bytes(b"x", filename="x.png")
        )


async def test_download_attachment_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "chattice.media._rest.download_media",
        lambda credentials, name, timeout: b"content",
    )
    data = await _bot(_AppCreds()).download_attachment("media/r1")
    assert data == b"content"


async def test_download_attachment_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "chattice.media._rest.download_media",
        lambda credentials, name, timeout: b"content",
    )
    destination = tmp_path / "out.bin"
    result = await _bot(_UserCreds()).download_attachment(
        "media/r1", destination=destination
    )
    assert result == destination
    assert destination.read_bytes() == b"content"


async def test_download_falls_back_to_user_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Credentials] = []

    def fake_download(
        credentials: Credentials, name: str, timeout: float | None
    ) -> bytes:
        captured.append(credentials)
        return b"content"

    class NarrowApp(_AppCreds):
        def __init__(self) -> None:
            super().__init__()
            self.scopes = ("https://www.googleapis.com/auth/other.only",)

    monkeypatch.setattr("chattice.media._rest.download_media", fake_download)
    user_credentials = _UserCreds()
    bot = Bot(
        app_credentials_provider=lambda: NarrowApp(),
        user_credentials_provider=lambda: user_credentials,
    )
    data = await bot.download_attachment("media/r1")
    assert data == b"content"
    assert captured[0] is user_credentials


async def test_download_without_any_identity_rejected() -> None:
    bot = Bot(credentials=_AppCreds())  # app creds with chat.bot — fine
    with pytest.raises(CapabilityNotSupported, match="no user identity"):
        await bot.upload_attachment("S1", InputFile.from_bytes(b"x", filename="x.png"))


async def test_download_drive_backed_rejected() -> None:
    ref = AttachmentRef(source=AttachmentSource.DRIVE_FILE, drive_file_id="d1")
    with pytest.raises(ChatAPIError, match="Drive"):
        await _bot(_AppCreds()).download_attachment(ref)


async def test_download_without_resource_name_rejected() -> None:
    ref = AttachmentRef(source=AttachmentSource.UPLOADED_CONTENT)
    with pytest.raises(ChatAPIError, match="resourceName"):
        await _bot(_AppCreds()).download_attachment(ref)


async def test_get_attachment_app_auth() -> None:
    from google.apps.chat_v1.types.attachment import Attachment, AttachmentDataRef

    name = "spaces/S/messages/M/attachments/A"
    transport = FakeChatTransport()
    transport.attachments[name] = Attachment(
        name=name,
        content_name="a.png",
        content_type="image/png",
        attachment_data_ref=AttachmentDataRef(resource_name="media/1"),
    )
    bot = Bot(credentials=_AppCreds(), transport=transport)
    ref = await bot.get_attachment(name)
    assert ref.name == name
    assert ref.is_uploaded
    assert ref.resource_name == "media/1"
    assert ref.filename == "a.png"


async def test_get_attachment_unknown_name_wraps_not_found() -> None:
    from chattice.client import ChatNotFoundError

    bot = Bot(credentials=_AppCreds(), transport=FakeChatTransport())
    with pytest.raises(ChatNotFoundError):
        await bot.get_attachment("spaces/S/messages/M/attachments/missing")


async def test_get_attachment_user_auth_rejected() -> None:
    with pytest.raises(CapabilityNotSupported, match="app authentication"):
        await _bot(_UserCreds()).get_attachment("spaces/S/messages/M/attachments/A")


async def test_send_message_rejects_private_to_with_attachments() -> None:
    transport = FakeChatTransport()
    bot = Bot(credentials=_AppCreds(), transport=transport)
    with pytest.raises(ChatAPIError, match="private_to"):
        await bot.send_message(
            "spaces/A",
            text="t",
            private_to="users/U",
            attachments=[InputFile.from_bytes(b"x", filename="x.png")],
        )
    assert transport.calls == []  # zero transport calls


async def test_send_message_rejects_accessory_widgets_with_attachments() -> None:
    from chattice.cards import AccessoryWidget, ButtonList

    transport = FakeChatTransport()
    bot = Bot(credentials=_AppCreds(), transport=transport)
    with pytest.raises(ChatAPIError, match="accessory widgets"):
        await bot.send_message(
            "spaces/A",
            text="t",
            accessory_widgets=[AccessoryWidget(button_list=ButtonList())],
            attachments=[InputFile.from_bytes(b"x", filename="x.png")],
        )
    assert transport.calls == []


async def test_send_message_rejects_cross_space_uploaded() -> None:
    transport = FakeChatTransport()
    bot = Bot(credentials=_AppCreds(), transport=transport)
    uploaded = UploadedAttachment(
        space="spaces/B",
        filename="x.png",
        attachment_data_ref={"resourceName": "media/r"},
    )
    with pytest.raises(ChatAPIError, match="scoped"):
        await bot.send_message("spaces/A", attachments=[uploaded])
    assert transport.calls == []


async def test_send_message_uploads_files_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uploaded: list[str] = []

    def fake_upload(
        credentials: Credentials,
        parent: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        timeout: float | None,
    ) -> dict[str, Any]:
        uploaded.append(filename)
        return {"attachmentDataRef": {"resourceName": f"media/{filename}"}}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    transport = FakeChatTransport()
    bot = Bot(credentials=_UserCreds(), transport=transport)
    await bot.send_message(
        "spaces/A",
        attachments=[
            InputFile.from_bytes(b"1", filename="one.png"),
            InputFile.from_bytes(b"2", filename="two.pdf"),
        ],
    )
    assert uploaded == ["one.png", "two.pdf"]
    request = transport.requests[-1]
    names = [a.attachment_data_ref.resource_name for a in request.message.attachment]
    assert names == ["media/one.png", "media/two.pdf"]


async def test_send_message_uploaded_attachment_skips_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[int] = []

    def fake_upload(*args: Any, **kwargs: Any) -> dict[str, Any]:
        called.append(1)
        return {}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    transport = FakeChatTransport()
    bot = Bot(credentials=_UserCreds(), transport=transport)
    uploaded = UploadedAttachment(
        space="spaces/A",
        filename="x.png",
        attachment_data_ref={
            "resourceName": "media/r",
            "attachmentUploadToken": "tok",
        },
    )
    await bot.send_message("spaces/A", attachments=[uploaded])
    assert called == []
    entry = transport.requests[-1].message.attachment[0]
    assert entry.attachment_data_ref.resource_name == "media/r"
    assert entry.attachment_data_ref.attachment_upload_token == "tok"


async def test_send_message_preflights_whole_set_before_first_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: list[int] = []

    def fake_upload(*args: Any, **kwargs: Any) -> dict[str, Any]:
        called.append(1)
        return {}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    transport = FakeChatTransport()
    bot = Bot(credentials=_UserCreds(), transport=transport)
    missing = tmp_path / "gone.png"
    with pytest.raises(FileNotFoundError):
        await bot.send_message(
            "spaces/A",
            attachments=[
                InputFile.from_bytes(b"1", filename="ok.png"),
                InputFile.from_path(str(missing)),
            ],
        )
    assert called == []  # the first file was never uploaded
    assert transport.calls == []


async def test_send_message_space_ref_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_upload(
        credentials: Credentials,
        parent: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        timeout: float | None,
    ) -> dict[str, Any]:
        return {"attachmentDataRef": {"resourceName": "media/x"}}

    monkeypatch.setattr("chattice.media._rest.upload_media", fake_upload)
    transport = FakeChatTransport()
    bot = Bot(credentials=_UserCreds(), transport=transport)
    await bot.send_message(
        SpaceRef(name="spaces/BBB"),
        text="with file",
        attachments=[InputFile.from_bytes(b"x", filename="x.png")],
    )
    assert transport.requests[-1].parent == "spaces/BBB"
    attachment = transport.requests[-1].message.attachment[0]
    assert attachment.attachment_data_ref.resource_name == "media/x"


async def test_bot_rejects_combined_identity_arguments() -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        Bot(
            credentials=_AppCreds(),
            user_credentials_provider=lambda: _UserCreds(),
        )
    with pytest.raises(ValueError, match="implied"):
        Bot(
            app_credentials_provider=lambda: _AppCreds(),
            auth_mode=AuthMode.APP,
        )
