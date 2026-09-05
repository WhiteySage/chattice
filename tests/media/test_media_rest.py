"""media/_rest.py: REST upload/download over fake googleapiclient modules."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import chattice.media._rest as rest
from chattice.client import ChatAPIError


class _HttpError(Exception):
    def __init__(self) -> None:
        super().__init__("boom")
        self.resp = SimpleNamespace(status=403)


class _FakeService:
    """Stand-in for the discovery service: records and fabricates."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def media(self) -> _FakeService:
        return self

    def upload(
        self, parent: str, body: dict[str, str], media_body: Any
    ) -> _FakeService:
        self.calls.append(("upload", parent, body, media_body))
        return self

    def execute(self) -> dict[str, Any]:
        return {"attachmentDataRef": {"resourceName": "media/r1"}}

    def download_media(self, resourceName: str) -> _FakeService:
        self.calls.append(("download_media", resourceName))
        return self


class _FakeUpload:
    def __init__(self, fd: Any, mimetype: str | None) -> None:
        self.fd = fd
        self.mimetype = mimetype


class _FakeDownload:
    def __init__(self, buffer: Any, request: Any) -> None:
        self.buffer = buffer
        self.request = request
        self.chunks: list[bytes] = [b"part1", b"part2", b""]

    def next_chunk(self) -> tuple[None, bool]:
        chunk = self.chunks.pop(0)
        self.buffer.write(chunk)
        return (None, chunk == b"")


def _fake_modules(
    monkeypatch: pytest.MonkeyPatch,
    service: _FakeService,
    *,
    download_cls: Any = _FakeDownload,
    import_error: Exception | None = None,
) -> None:
    def fake_import(module: str) -> Any:
        if import_error is not None:
            raise import_error
        if module == "googleapiclient.discovery":
            return SimpleNamespace(build=lambda *args, **kwargs: service)
        if module == "googleapiclient.errors":
            return SimpleNamespace(HttpError=_HttpError)
        if module == "googleapiclient.http":
            return SimpleNamespace(
                MediaIoBaseUpload=_FakeUpload,
                MediaIoBaseDownload=download_cls,
            )
        if module == "httplib2":
            return SimpleNamespace(Http=lambda timeout: SimpleNamespace())
        if module == "google_auth_httplib2":
            return SimpleNamespace(AuthorizedHttp=lambda creds, http: http)
        raise ImportError(f"no fake module for {module}")

    monkeypatch.setattr(rest, "_import_extra", fake_import)


def test_upload_media_success(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()
    _fake_modules(monkeypatch, service)
    result = rest.upload_media(None, "spaces/A", "x.png", "image/png", b"data", None)
    assert result["attachmentDataRef"]["resourceName"] == "media/r1"
    assert service.calls[0][0] == "upload"
    assert service.calls[0][1] == "spaces/A"
    assert service.calls[0][2] == {"filename": "x.png"}


def test_upload_media_mimetype_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()
    _fake_modules(monkeypatch, service)
    rest.upload_media(None, "spaces/A", "x.bin", None, b"data", None)
    media = service.calls[0][3]
    assert media.mimetype == "application/octet-stream"


def test_upload_media_timeout_builds_authorized_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeService()
    _fake_modules(monkeypatch, service)
    rest.upload_media(None, "spaces/A", "x.png", "image/png", b"d", 30.0)
    assert service.calls[0][0] == "upload"


def test_upload_media_http_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()

    def explode() -> dict[str, Any]:
        raise _HttpError()

    service.execute = explode  # type: ignore[method-assign]
    _fake_modules(monkeypatch, service)
    with pytest.raises(ChatAPIError, match=r"upload failed.*403"):
        rest.upload_media(None, "spaces/A", "x.png", "image/png", b"d", None)


def test_upload_media_transport_error_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeService()

    def explode() -> dict[str, Any]:
        raise ConnectionError("network down")

    service.execute = explode  # type: ignore[method-assign]
    _fake_modules(monkeypatch, service)
    with pytest.raises(ChatAPIError, match="upload failed"):
        rest.upload_media(None, "spaces/A", "x.png", "image/png", b"d", None)


def test_download_media_success(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeService()
    _fake_modules(monkeypatch, service)
    data = rest.download_media(None, "media/r1", None)
    assert data == b"part1part2"
    assert service.calls[0] == ("download_media", "media/r1")


def test_download_media_transport_error_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExplodingDownload(_FakeDownload):
        def next_chunk(self) -> tuple[None, bool]:
            raise ConnectionError("network down")

    service = _FakeService()
    _fake_modules(monkeypatch, service, download_cls=ExplodingDownload)
    with pytest.raises(ChatAPIError, match="download failed"):
        rest.download_media(None, "media/r1", None)


def test_download_media_http_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    class ExplodingDownload(_FakeDownload):
        def next_chunk(self) -> tuple[None, bool]:
            raise _HttpError()

    service = _FakeService()
    _fake_modules(monkeypatch, service, download_cls=ExplodingDownload)
    with pytest.raises(ChatAPIError, match=r"download failed.*403"):
        rest.download_media(None, "media/r1", None)


def test_import_extra_missing_gives_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ModuleNotFoundError(
        "No module named 'googleapiclient.discovery'",
        name="googleapiclient.discovery",
    )

    def raise_error(module: str) -> Any:
        raise error

    monkeypatch.setattr("importlib.import_module", raise_error)
    with pytest.raises(ChatAPIError, match=r"chattice\[media\]"):
        rest._import_extra("googleapiclient.discovery")


def test_import_extra_broken_install_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ModuleNotFoundError(
        "No module named 'googleapis_common_protos'", name="googleapis_common_protos"
    )

    def raise_error(module: str) -> Any:
        raise error

    monkeypatch.setattr("importlib.import_module", raise_error)
    with pytest.raises(ModuleNotFoundError):
        rest._import_extra("googleapiclient.discovery")
