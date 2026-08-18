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
    """Lazy-import a module of the optional media extra.

    ``importlib`` keeps the untyped third-party extra out of mypy's
    sight entirely. A missing extra surfaces as the actionable error
    below; an ImportError raised from INSIDE an installed module is
    re-raised untouched (that is a broken install, not a missing one).
    """
    try:
        return importlib.import_module(module)
    except ImportError as error:
        missing = getattr(error, "name", None)
        if (
            missing is not None
            and missing != module
            and missing != module.split(".")[0]
        ):
            raise
        raise ChatAPIError(
            "Media upload/download requires the optional 'media' extra; "
            f"install it with: {_MEDIA_EXTRA_INSTALL}"
        ) from error


def _service(credentials: Any, timeout: float | None) -> Any:
    """Build the discovery service for the credentials.

    ``discovery.build`` rejects ``credentials=`` combined with ``http=``
    (they are mutually exclusive), so the timeout path builds an
    authorized httplib2 transport first and passes ONLY ``http=`` — the
    same official ``google_auth_httplib2.AuthorizedHttp`` that
    ``build(credentials=...)`` installs internally, including its
    refresh-and-retry-on-401 behavior.
    """
    discovery = _import_extra("googleapiclient.discovery")
    if timeout is None:
        return discovery.build("chat", "v1", credentials=credentials)
    httplib2 = _import_extra("httplib2")
    authorized = _import_extra("google_auth_httplib2").AuthorizedHttp
    http = authorized(credentials, httplib2.Http(timeout=timeout))
    return discovery.build("chat", "v1", http=http)


def _wrap_media_error(error: Exception, action: str) -> ChatAPIError:
    """Wrap SDK and transport-level failures into the Chattice error type."""
    status = getattr(getattr(error, "resp", None), "status", None)
    detail = f" ({status})" if status else ""
    return ChatAPIError(f"media {action} failed{detail}: {error}")


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

    media = MediaIoBaseUpload(
        io.BytesIO(data),
        mimetype=content_type or "application/octet-stream",
    )
    try:
        return cast(
            dict[str, Any],
            service.media()
            .upload(parent=parent, body={"filename": filename}, media_body=media)
            .execute(),
        )
    except HttpError as error:
        raise _wrap_media_error(error, "upload") from error
    except Exception as error:
        raise _wrap_media_error(error, "upload") from error


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
        raise _wrap_media_error(error, "download") from error
    except Exception as error:
        raise _wrap_media_error(error, "download") from error
    return buffer.getvalue()
