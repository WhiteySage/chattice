"""Google Cloud Storage AssetPublisher (optional extra chattice[gcs])."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from uuid import uuid4

from chattice.exceptions import AssetPublishError


def _load_storage() -> Any:
    try:
        from google.cloud import storage  # type: ignore[import-untyped]
    except ImportError as error:
        raise ImportError(
            "GCSAssetPublisher requires the optional dependency; "
            'install "chattice[gcs]"'
        ) from error
    return storage


def _prefix(value: str) -> str:
    if value.startswith("/") or ".." in Path(value).parts:
        raise ValueError(
            "GCS namespace prefixes must be relative and cannot contain '..'"
        )
    return f"{value.rstrip('/')}/" if value else ""


class GCSAssetPublisher:
    """Publish non-sensitive Card images to a preconfigured GCS bucket.

    The bucket or ``public_url_base`` must already expose uploaded objects
    over anonymous HTTPS. This integration never changes bucket IAM. Cache
    metadata is opt-in and never grants public access to an object.
    """

    def __init__(
        self,
        *,
        bucket: str,
        namespaces: Mapping[str, str] | None = None,
        default_namespace: str | None = None,
        client: Any = None,
        credentials: Any = None,
        project: str | None = None,
        public_url_base: str | None = None,
        upload_timeout: float = 60.0,
        cache_control: str | None = None,
    ) -> None:
        if not bucket or bucket != bucket.strip():
            raise ValueError("bucket must be a non-empty GCS bucket name")
        if upload_timeout <= 0:
            raise ValueError("upload_timeout must be positive")
        if client is not None and (credentials is not None or project is not None):
            raise ValueError(
                "client cannot be combined with credentials or project; configure "
                "the supplied client directly"
            )
        mapping = dict(namespaces or {})
        for namespace, prefix in mapping.items():
            if not namespace or namespace != namespace.strip():
                raise ValueError("namespace keys must be non-empty logical names")
            mapping[namespace] = _prefix(prefix)
        if default_namespace is not None and default_namespace not in mapping:
            raise ValueError("default_namespace must be a key in namespaces")
        if public_url_base is None:
            public_url_base = f"https://storage.googleapis.com/{quote(bucket, safe='')}"
        parsed_url_base = urlparse(public_url_base)
        if parsed_url_base.scheme != "https" or not parsed_url_base.netloc:
            raise ValueError("public_url_base must be an absolute HTTPS URL")

        if client is None:
            storage = _load_storage()
            client = storage.Client(project=project, credentials=credentials)
        self._bucket = client.bucket(bucket)
        self._namespaces = mapping
        self._default_namespace = default_namespace
        self._public_url_base = public_url_base.rstrip("/")
        self._upload_timeout = upload_timeout
        self._cache_control = cache_control

    def _object_name(self, filename: str, namespace: str | None) -> str:
        if not filename or Path(filename).name != filename or "\\" in filename:
            raise AssetPublishError("filename must be a non-empty basename")
        effective_namespace = (
            self._default_namespace if namespace is None else namespace
        )
        if effective_namespace is None:
            prefix = ""
        else:
            try:
                prefix = self._namespaces[effective_namespace]
            except KeyError as error:
                raise AssetPublishError(
                    f"Unknown GCS asset namespace {effective_namespace!r}"
                ) from error
        return f"{prefix}{uuid4().hex}-{filename}"

    async def publish(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        namespace: str | None = None,
    ) -> str:
        """Upload bytes off the event loop and return their public HTTPS URL."""
        object_name = self._object_name(filename, namespace)
        blob = self._bucket.blob(object_name)
        if self._cache_control is not None:
            blob.cache_control = self._cache_control
        await asyncio.to_thread(
            blob.upload_from_string,
            data,
            content_type=content_type,
            timeout=self._upload_timeout,
        )
        return f"{self._public_url_base}/{quote(object_name, safe='/')}"


__all__ = ["GCSAssetPublisher"]
