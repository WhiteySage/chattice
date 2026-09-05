"""MessageEvent.attachment_refs: typed additive accessor over raw mappings."""

from __future__ import annotations

from chattice.events import MessageEvent


def _event(attachments: list[dict[str, object]] | None) -> MessageEvent:
    raw = {"chat": {"message": {"attachment": attachments or []}}}
    return MessageEvent(text="hi", raw=raw)


def test_attachment_refs_typed_view() -> None:
    event = _event(
        [
            {
                "contentName": "report.pdf",
                "contentType": "application/pdf",
                "attachmentDataRef": {"resourceName": "media/1"},
            },
            {
                "contentName": "doc.docx",
                "driveDataRef": {"driveFileId": "d9"},
            },
        ]
    )
    refs = event.attachment_refs
    assert len(refs) == 2
    assert refs[0].is_uploaded
    assert refs[0].filename == "report.pdf"
    assert refs[0].resource_name == "media/1"
    assert refs[1].is_drive
    assert refs[1].drive_file_id == "d9"


def test_attachment_refs_empty_without_attachments() -> None:
    event = MessageEvent(text="hi", raw={})
    assert event.attachment_refs == ()
    assert event.attachments == ()
