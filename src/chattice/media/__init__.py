"""Media and attachment primitives (Google Chat media semantics).

Two distinct Google surfaces exist, and this package keeps them apart:

* **Card Image** — an HTTPS-hosted picture rendered inside a card
  (``chattice.cards.Image``). URL-only; local paths and bytes are not
  Card images.
* **Message attachment** — a file uploaded to Google Chat through the
  media API (``InputFile`` → ``Bot.upload_attachment`` or
  ``send_message(attachments=...)``) and referenced by
  ``attachmentDataRef`` on the wire. Uploading requires USER
  authentication; a service-account/app-auth Bot cannot upload files.

There is one canonical file model — :class:`InputFile` — no separate
Photo/Document/Video entities. Inbound attachments are typed through
:class:`AttachmentRef` while the raw lossless
``MessageEvent.attachments`` mappings remain unchanged.
"""

from __future__ import annotations

import mimetypes
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from chattice._json_snapshot import deep_snapshot

__all__ = [
    "MAX_ATTACHMENT_SIZE_BYTES",
    "AttachmentRef",
    "AttachmentSource",
    "InputFile",
    "UploadedAttachment",
]

# Documented Google Chat upload ceiling (200 MB). Google publishes no
# minimum size: zero-byte files are allowed and never rejected locally.
MAX_ATTACHMENT_SIZE_BYTES = 200 * 1024 * 1024


class AttachmentSource(Enum):
    """Google's attachment data-ref kinds (oneof ``data_ref``)."""

    UPLOADED_CONTENT = "UPLOADED_CONTENT"
    DRIVE_FILE = "DRIVE_FILE"


def _validate_filename(filename: str) -> str:
    name = filename.strip()
    if not name:
        raise ValueError("attachment filename must not be empty")
    if "/" in name or "\\" in name:
        raise ValueError(
            f"attachment filename must be a bare file name, not a path; got {name!r}"
        )
    if not os.path.splitext(name)[1]:
        raise ValueError(
            "attachment filename must include an extension (Google requires "
            f"a filename with an extension); got {name!r}"
        )
    return name


def _guess_content_type(filename: str) -> str:
    guessed, _encoding = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


@dataclass(frozen=True, slots=True)
class InputFile:
    """A local file to upload as a Google Chat attachment.

    Create through :meth:`from_path` (deferred read — the file is only
    opened on the upload path) or :meth:`from_bytes` (immutable in-memory
    snapshot). Use ``InputFile`` for every local artifact.
    """

    filename: str
    content_type: str | None
    _path: str | None = field(default=None, repr=False)
    _data: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None and self._data is None:
            raise ValueError(
                "InputFile requires a source — use from_path() or "
                "from_bytes() instead of the raw constructor"
            )

    @classmethod
    def from_path(
        cls,
        path: str | os.PathLike[str],
        *,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> InputFile:
        """Reference a local file without reading its content.

        Only regular files are accepted (directories, FIFOs and devices
        are rejected locally); the 200 MB ceiling is checked from
        ``stat`` without touching the content.
        """
        raw = os.fspath(path)
        if not os.path.exists(raw):
            raise FileNotFoundError(f"attachment file does not exist: {raw!r}")
        if not stat.S_ISREG(os.stat(raw).st_mode):
            raise ValueError(
                "attachment path must be a regular file "
                f"(directory/FIFO/device are not uploadable); got {raw!r}"
            )
        size = os.path.getsize(raw)
        if size > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(
                f"attachment exceeds the 200 MB Google upload limit: {size} bytes"
            )
        name = _validate_filename(filename or os.path.basename(raw))
        return cls(
            filename=name,
            content_type=content_type or _guess_content_type(name),
            _path=raw,
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray | memoryview,
        *,
        filename: str,
        content_type: str | None = None,
    ) -> InputFile:
        """Wrap an immutable in-memory snapshot of file content."""
        name = _validate_filename(filename)
        snapshot = bytes(data)
        if len(snapshot) > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(
                "attachment exceeds the 200 MB Google upload limit: "
                f"{len(snapshot)} bytes"
            )
        return cls(
            filename=name,
            content_type=content_type or _guess_content_type(name),
            _data=snapshot,
        )

    @property
    def size(self) -> int:
        """Current byte size without reading the file content."""
        if self._data is not None:
            return len(self._data)
        return os.path.getsize(self._path)  # type: ignore[arg-type]

    def validate(self) -> None:
        """Re-check local invariants without reading content (preflight).

        A path-backed file can change between construction and upload;
        existence, regular-file kind and the 200 MB ceiling are
        re-checked here, before any transport work.
        """
        if self._data is not None:
            return
        raw = self._path
        assert raw is not None  # guarded by __post_init__
        try:
            mode = os.stat(raw).st_mode
            size = os.path.getsize(raw)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"attachment file disappeared: {raw!r}") from error
        if not stat.S_ISREG(mode):
            raise ValueError(f"attachment path stopped being a regular file: {raw!r}")
        if size > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError("attachment grew past the 200 MB Google upload limit")

    def read(self) -> bytes:
        """Read the content on the upload path (open-once validation).

        The file is opened a SINGLE time and every check runs against
        that descriptor: ``open(path)`` → ``fstat(fd)`` → regular-file
        and size guards → read from the same ``fd``. There is no
        ``stat(path)`` → later ``open(path)`` window left to race.
        ``O_NONBLOCK`` makes opening a FIFO (or a path swapped onto one)
        fail closed instead of hanging the worker: the descriptor check
        rejects it as non-regular. Regular symlinks are honored.
        """
        if self._data is not None:
            return self._data
        raw = self._path
        assert raw is not None  # guarded by __post_init__
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(raw, flags)
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"attachment path is not a regular file: {raw!r}")
            if file_stat.st_size > MAX_ATTACHMENT_SIZE_BYTES:
                raise ValueError("attachment grew past the 200 MB Google upload limit")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(fd)


@dataclass(frozen=True, slots=True)
class UploadedAttachment:
    """An attachment uploaded into one specific Space.

    Remembers the parent Space so a cross-Space send is rejected locally
    instead of being dropped by Google. The wire mappings are deep-
    snapshotted at construction so a frozen instance cannot be mutated
    through a caller's dict.
    """

    space: str
    filename: str
    attachment_data_ref: Mapping[str, object]
    raw: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attachment_data_ref",
            cast(
                Mapping[str, object],
                deep_snapshot(self.attachment_data_ref, where="UploadedAttachment"),
            ),
        )
        if self.raw is not None:
            object.__setattr__(
                self,
                "raw",
                cast(
                    Mapping[str, object],
                    deep_snapshot(self.raw, where="UploadedAttachment.raw"),
                ),
            )


def _ref_text(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachmentRef:
    """Typed inbound attachment metadata (additive read-side accessor).

    ``MessageEvent.attachments`` stays a lossless tuple of raw mappings;
    ``MessageEvent.attachment_refs`` adds this typed view on top.
    ``thumbnail_uri``/``download_uri`` are human-facing links; code that
    downloads content must use ``attachment_data_ref.resourceName`` via
    ``Bot.download_attachment``.
    """

    name: str | None = None
    content_name: str | None = None
    content_type: str | None = None
    source: AttachmentSource | None = None
    attachment_data_ref: Mapping[str, object] | None = None
    drive_file_id: str | None = None
    thumbnail_uri: str | None = None
    download_uri: str | None = None
    raw: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Deep-snapshot the wire mappings so the frozen facade cannot be
        # mutated through a caller's dict after construction.
        if self.attachment_data_ref is not None:
            object.__setattr__(
                self,
                "attachment_data_ref",
                cast(
                    Mapping[str, object],
                    deep_snapshot(
                        self.attachment_data_ref,
                        where="AttachmentRef.attachment_data_ref",
                    ),
                ),
            )
        object.__setattr__(
            self,
            "raw",
            cast(
                Mapping[str, object],
                deep_snapshot(self.raw, where="AttachmentRef.raw"),
            ),
        )

    @property
    def is_uploaded(self) -> bool:
        """Whether Google stored the content in Chat (UPLOADED_CONTENT)."""
        return self.source is AttachmentSource.UPLOADED_CONTENT

    @property
    def is_drive(self) -> bool:
        """Whether this references a Google Drive file (DRIVE_FILE)."""
        return self.source is AttachmentSource.DRIVE_FILE

    @property
    def filename(self) -> str | None:
        """The original file name (``contentName`` on the wire)."""
        return self.content_name

    @property
    def mime_type(self) -> str | None:
        """The MIME content type (``contentType`` on the wire)."""
        return self.content_type

    @property
    def resource_name(self) -> str | None:
        """``attachmentDataRef.resourceName`` — the media.download handle."""
        if self.attachment_data_ref is None:
            return None
        return _ref_text(self.attachment_data_ref, "resourceName") or _ref_text(
            self.attachment_data_ref, "resource_name"
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> AttachmentRef:
        """Build from a Google wire mapping (camelCase JSON fields)."""
        data_ref = mapping.get("attachmentDataRef")
        attachment_data_ref = (
            cast(Mapping[str, object], data_ref)
            if isinstance(data_ref, Mapping)
            else None
        )
        drive_ref = mapping.get("driveDataRef")
        drive_file_id = None
        source: AttachmentSource | None = None
        if attachment_data_ref is not None:
            source = AttachmentSource.UPLOADED_CONTENT
        elif isinstance(drive_ref, Mapping):
            source = AttachmentSource.DRIVE_FILE
            drive_file_id = _ref_text(drive_ref, "driveFileId")
        return cls(
            name=_ref_text(mapping, "name"),
            content_name=_ref_text(mapping, "contentName"),
            content_type=_ref_text(mapping, "contentType"),
            source=source,
            attachment_data_ref=attachment_data_ref,
            drive_file_id=drive_file_id,
            thumbnail_uri=_ref_text(mapping, "thumbnailUri"),
            download_uri=_ref_text(mapping, "downloadUri"),
            raw=mapping,
        )

    @classmethod
    def from_proto(cls, proto: Any) -> AttachmentRef:
        """Build from an SDK ``Attachment`` proto (GAPIC get_attachment)."""
        attachment_data_ref = None
        source: AttachmentSource | None = None
        if proto._pb.HasField("attachment_data_ref"):
            attachment_data_ref = {
                "resourceName": proto.attachment_data_ref.resource_name,
                "attachmentUploadToken": (
                    proto.attachment_data_ref.attachment_upload_token
                ),
            }
            source = AttachmentSource.UPLOADED_CONTENT
        drive_file_id = None
        if proto._pb.HasField("drive_data_ref"):
            source = AttachmentSource.DRIVE_FILE
            drive_file_id = proto.drive_data_ref.drive_file_id
        return cls(
            name=proto.name or None,
            content_name=proto.content_name or None,
            content_type=proto.content_type or None,
            source=source,
            attachment_data_ref=attachment_data_ref,
            drive_file_id=drive_file_id,
            thumbnail_uri=proto.thumbnail_uri or None,
            download_uri=proto.download_uri or None,
        )
