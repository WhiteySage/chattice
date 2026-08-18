"""Typed inbound AttachmentRef: wire mapping and SDK proto parsing."""

from __future__ import annotations

from google.apps.chat_v1.types.attachment import Attachment, AttachmentDataRef

from chattice.media import AttachmentRef, AttachmentSource


def test_from_mapping_uploaded_content() -> None:
    ref = AttachmentRef.from_mapping(
        {
            "name": "spaces/S/messages/M/attachments/A",
            "contentName": "report.pdf",
            "contentType": "application/pdf",
            "attachmentDataRef": {
                "resourceName": "media/xyz",
                "attachmentUploadToken": "tok",
            },
            "thumbnailUri": "https://example.com/thumb",
            "downloadUri": "https://example.com/dl",
        }
    )
    assert ref.is_uploaded
    assert not ref.is_drive
    assert ref.filename == "report.pdf"
    assert ref.mime_type == "application/pdf"
    assert ref.resource_name == "media/xyz"
    assert ref.attachment_data_ref is not None
    assert ref.attachment_data_ref["attachmentUploadToken"] == "tok"
    assert ref.thumbnail_uri == "https://example.com/thumb"
    assert ref.download_uri == "https://example.com/dl"


def test_from_mapping_drive_file() -> None:
    ref = AttachmentRef.from_mapping(
        {"driveDataRef": {"driveFileId": "d123"}, "contentName": "doc.docx"}
    )
    assert ref.is_drive
    assert not ref.is_uploaded
    assert ref.drive_file_id == "d123"
    assert ref.resource_name is None
    assert ref.filename == "doc.docx"


def test_from_proto_drive() -> None:
    from google.apps.chat_v1.types.attachment import DriveDataRef

    proto = Attachment(
        name="spaces/S/messages/M/attachments/A",
        content_name="doc.docx",
        drive_data_ref=DriveDataRef(drive_file_id="d9"),
    )
    ref = AttachmentRef.from_proto(proto)
    assert ref.is_drive
    assert ref.drive_file_id == "d9"
    assert ref.filename == "doc.docx"


def test_attachment_ref_snapshots_raw_mapping() -> None:
    from collections.abc import Mapping
    from typing import cast

    raw: dict[str, object] = {
        "attachmentDataRef": {"resourceName": "media/1"},
        "contentName": "a.png",
    }
    ref = AttachmentRef.from_mapping(raw)
    inner = raw["attachmentDataRef"]
    assert isinstance(inner, dict)
    inner["resourceName"] = "media/evil"
    assert ref.resource_name == "media/1"
    ref_data = cast(Mapping[str, object], ref.raw["attachmentDataRef"])
    assert ref_data["resourceName"] == "media/1"


def test_from_proto_uploaded() -> None:
    proto = Attachment(
        name="spaces/S/messages/M/attachments/A",
        content_name="a.png",
        content_type="image/png",
        attachment_data_ref=AttachmentDataRef(
            resource_name="media/1", attachment_upload_token="t"
        ),
        thumbnail_uri="https://example.com/thumb",
        download_uri="https://example.com/dl",
    )
    ref = AttachmentRef.from_proto(proto)
    assert ref.is_uploaded
    assert ref.resource_name == "media/1"
    assert ref.attachment_data_ref is not None
    assert ref.attachment_data_ref["attachmentUploadToken"] == "t"
    assert ref.thumbnail_uri == "https://example.com/thumb"
    assert ref.download_uri == "https://example.com/dl"
    assert ref.source is AttachmentSource.UPLOADED_CONTENT


def test_from_mapping_without_data_ref() -> None:
    ref = AttachmentRef.from_mapping({"contentName": "odd.bin"})
    assert not ref.is_uploaded
    assert not ref.is_drive
    assert ref.source is None
    assert ref.resource_name is None
