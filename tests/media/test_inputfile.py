"""InputFile construction and local validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from chattice.media import InputFile


def test_from_path_reference_without_reading(tmp_path: Path) -> None:
    path = tmp_path / "out3.png"
    path.write_bytes(b"\x89PNG\r\n")
    file = InputFile.from_path(str(path))
    assert file.filename == "out3.png"
    assert file.content_type == "image/png"
    assert file.size == 6
    assert file.read() == b"\x89PNG\r\n"


def test_from_path_mime_fallback(tmp_path: Path) -> None:
    path = tmp_path / "blob.weirdx"
    path.write_bytes(b"x")
    assert InputFile.from_path(str(path)).content_type == "application/octet-stream"


def test_from_path_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        InputFile.from_path("/nonexistent/xx.png")


def test_from_path_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="regular file"):
        InputFile.from_path(str(tmp_path))


def test_from_path_empty_filename_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="empty"):
        InputFile.from_path(str(path), filename="   ")


def test_from_path_filename_with_slash_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="bare file name"):
        InputFile.from_path(str(path), filename="sub/x.png")


def test_from_path_filename_without_extension_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="extension"):
        InputFile.from_path(str(path), filename="report")


def test_from_path_over_size_limit_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("chattice.media.MAX_ATTACHMENT_SIZE_BYTES", 10)
    path = tmp_path / "big.png"
    path.write_bytes(b"x" * 11)
    with pytest.raises(ValueError, match="200 MB"):
        InputFile.from_path(str(path))


def test_from_path_zero_byte_allowed(tmp_path: Path) -> None:
    # Google documents a 200 MB maximum but no minimum size; zero-byte
    # files are NOT rejected by the framework.
    path = tmp_path / "empty.png"
    path.write_bytes(b"")
    file = InputFile.from_path(str(path))
    assert file.size == 0
    assert file.read() == b""


def test_validate_rechecks_changed_file(tmp_path: Path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(b"x")
    file = InputFile.from_path(str(path))
    path.unlink()
    with pytest.raises(FileNotFoundError):
        file.read()


def test_from_bytes_snapshot() -> None:
    file = InputFile.from_bytes(b"\x89PNG", filename="result.png")
    assert file.filename == "result.png"
    assert file.content_type == "image/png"
    assert file.size == 4
    assert file.read() == b"\x89PNG"


def test_from_bytes_requires_filename() -> None:
    with pytest.raises(ValueError, match="empty"):
        InputFile.from_bytes(b"x", filename="")


def test_from_bytes_filename_validation() -> None:
    with pytest.raises(ValueError, match="extension"):
        InputFile.from_bytes(b"x", filename="report")
    with pytest.raises(ValueError, match="bare file name"):
        InputFile.from_bytes(b"x", filename="a\\b.png")


def test_from_bytes_over_size_limit_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.media.MAX_ATTACHMENT_SIZE_BYTES", 10)
    with pytest.raises(ValueError, match="200 MB"):
        InputFile.from_bytes(b"x" * 11, filename="x.png")


def test_from_bytes_accepts_bytearray_snapshot() -> None:
    source = bytearray(b"data")
    file = InputFile.from_bytes(source, filename="x.bin")
    source[0] = ord("X")
    assert file.read() == b"data"


def test_raw_constructor_without_source_rejected() -> None:
    with pytest.raises(ValueError, match="from_path"):
        InputFile(filename="x.png", content_type="image/png")


def test_uploaded_attachment_snapshots_mapping() -> None:
    from chattice.media import UploadedAttachment

    ref = {"resourceName": "media/r1"}
    uploaded = UploadedAttachment(
        space="spaces/A", filename="x.png", attachment_data_ref=ref
    )
    ref["resourceName"] = "media/evil"
    assert uploaded.attachment_data_ref["resourceName"] == "media/r1"
