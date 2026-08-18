"""REST media transport (the optional ``chattice[media]`` extra).

The GAPIC ``google-apps-chat`` client cannot carry a binary media body:
its ``UploadAttachmentRequest`` carries only ``parent`` + ``filename``
(verified against 0.10.4, the current public minimum). The official
Python upload/download flow is the Google API Client Library media
endpoints, so Chattice reuses that as an optional dependency instead of
hand-rolling resumable uploads.

Everything here performs synchronous blocking I/O; callers run it
through ``asyncio.to_thread``.
"""

from __future__ import annotations

import importlib
from typing import Any

from chattice.client.errors import ChatAPIError

_MEDIA_EXTRA_INSTALL = 'pip install "chattice[media]"'


def _import_extra(module: str) -> Any:
    """Lazy-import a googleapiclient module (untyped third-party extra).

    ``importlib`` keeps the optional media extra out of mypy's sight
    entirely, so a missing extra surfaces as the actionable ImportError
    below rather than an import-time failure.
    """
    try:
        return importlib.import_module(module)
    except ImportError as error:
        raise ChatAPIError(
            "Media upload/download requires the optional 'media' extra; "
            f"install it with: {_MEDIA_EXTRA_INSTALL}"
        ) from error


class _AuthorizedHttp:
    """httplib2.Http authorized by google-auth credentials.

    A small local replacement for the removed ``AuthorizedHttp`` helper:
    google-auth's httplib2 transport no longer ships, while the media
    extra still depends on httplib2 via google-api-python-client. The
    credentials' ``before_request`` hook performs the same authorization
    (and refreshes expired user tokens) the legacy helper did.
    """

    def __init__(self, credentials: Any, timeout: float):
        httplib2 = _import_extra("httplib2")

        self._http = httplib2.Http(timeout=timeout)
        self._credentials = credentials

    def request(
        self,
        uri: str,
        method: str = "GET",
        body: Any = None,
        headers: Any = None,
        **kwargs: Any,
    ) -> Any:
        if headers is None:
            headers = {}
        self._credentials.before_request(self, method, uri, headers)
        return self._http.request(uri, method, body, headers, **kwargs)


def _service(credentials: Any, timeout: float | None) -> Any:
    discovery = _import_extra("googleapiclient.discovery")
    http: Any = None
    if timeout is not None:
        http = _AuthorizedHttp(credentials, timeout)
    return discovery.build("chat", "v1", credentials=credentials, http=http)


def upload_media(
    credentials: Any,
    parent: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    timeout: float | None,
) -> dict[str, Any]:
    """Upload bytes through the REST media.upload endpoint (blocking)."""
    import io
    from typing import cast

    service = _service(credentials, timeout)  # resolves the lazy extra first
    HttpError = _import_extra("googleapiclient.errors").HttpError
    MediaIoBaseUpload = _import_extra("googleapiclient.http").MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=content_type)
    try:
        return cast(
            dict[str, Any],
            service.media()
            .upload(parent=parent, body={"filename": filename}, media_body=media)
            .execute(),
        )
    except HttpError as error:
        raise ChatAPIError(
            f"media upload failed ({error.resp.status}): {error}"
        ) from error


def download_media(
    credentials: Any,
    resource_name: str,
    timeout: float | None,
) -> bytes:
    """Download bytes through the REST media.download endpoint (blocking)."""
    import io

    service = _service(credentials, timeout)  # resolves the lazy extra first
    HttpError = _import_extra("googleapiclient.errors").HttpError
    MediaIoBaseDownload = _import_extra("googleapiclient.http").MediaIoBaseDownload

    buffer = io.BytesIO()
    try:
        request = service.media().download_media(resourceName=resource_name)
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
    except HttpError as error:
        raise ChatAPIError(
            f"media download failed ({error.resp.status}): {error}"
        ) from error
    return buffer.getvalue()
