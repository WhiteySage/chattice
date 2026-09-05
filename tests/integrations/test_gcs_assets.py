"""GCS AssetPublisher mapping and upload behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

import chattice.integrations.gcs as gcs
from chattice.exceptions import AssetPublishError
from chattice.integrations.gcs import GCSAssetPublisher


@dataclass
class FakeBlob:
    name: str
    cache_control: str | None = None
    uploads: list[dict[str, object]] = field(default_factory=list)

    def upload_from_string(
        self,
        data: bytes,
        *,
        content_type: str,
        timeout: float,
    ) -> None:
        self.uploads.append(
            {
                "data": data,
                "content_type": content_type,
                "timeout": timeout,
            }
        )


@dataclass
class FakeBucket:
    name: str
    blobs: list[FakeBlob] = field(default_factory=list)

    def blob(self, name: str) -> FakeBlob:
        blob = FakeBlob(name)
        self.blobs.append(blob)
        return blob


@dataclass
class FakeClient:
    requested_buckets: list[str] = field(default_factory=list)
    buckets: dict[str, FakeBucket] = field(default_factory=dict)

    def bucket(self, name: str) -> FakeBucket:
        self.requested_buckets.append(name)
        return self.buckets.setdefault(name, FakeBucket(name))


def _publisher(client: FakeClient, **kwargs: Any) -> GCSAssetPublisher:
    return GCSAssetPublisher(
        bucket="chat-assets",
        namespaces={"reports": "reports/", "previews": "tmp/previews"},
        default_namespace="reports",
        client=client,
        **kwargs,
    )


async def test_gcs_publisher_uses_bucket_prefix_type_and_bytes() -> None:
    client = FakeClient()
    publisher = _publisher(client, upload_timeout=12.5)

    url = await publisher.publish(
        b"png-bytes",
        filename="report.png",
        content_type="image/png",
        namespace="previews",
    )

    assert client.requested_buckets == ["chat-assets"]
    blob = client.buckets["chat-assets"].blobs[0]
    assert blob.name.startswith("tmp/previews/")
    assert blob.name.endswith("-report.png")
    assert blob.uploads == [
        {
            "data": b"png-bytes",
            "content_type": "image/png",
            "timeout": 12.5,
        }
    ]
    assert blob.cache_control is None
    assert url == f"https://storage.googleapis.com/chat-assets/{blob.name}"


async def test_gcs_publisher_uses_default_namespace_and_unique_names() -> None:
    client = FakeClient()
    publisher = _publisher(client)

    first = await publisher.publish(
        b"one", filename="report.png", content_type="image/png"
    )
    second = await publisher.publish(
        b"two", filename="report.png", content_type="image/png"
    )

    blobs = client.buckets["chat-assets"].blobs
    assert all(blob.name.startswith("reports/") for blob in blobs)
    assert blobs[0].name != blobs[1].name
    assert first != second


async def test_gcs_publisher_rejects_unknown_namespace() -> None:
    publisher = _publisher(FakeClient())

    with pytest.raises(AssetPublishError, match="Unknown GCS asset namespace"):
        await publisher.publish(
            b"image",
            filename="image.png",
            content_type="image/png",
            namespace="unknown",
        )


async def test_gcs_publisher_supports_public_cdn_base_and_url_encoding() -> None:
    client = FakeClient()
    publisher = _publisher(
        client,
        public_url_base="https://cdn.example.com/chat-assets/",
        cache_control="public, max-age=31536000, immutable",
    )

    url = await publisher.publish(
        b"image",
        filename="daily report.png",
        content_type="image/png",
    )

    blob = client.buckets["chat-assets"].blobs[0]
    assert "%20" in url
    assert url == f"https://cdn.example.com/chat-assets/{blob.name.replace(' ', '%20')}"
    assert blob.cache_control == "public, max-age=31536000, immutable"


def test_gcs_publisher_requires_mapping_for_named_namespace() -> None:
    publisher = GCSAssetPublisher(bucket="assets", client=FakeClient())

    with pytest.raises(AssetPublishError, match="Unknown GCS asset namespace"):
        publisher._object_name("image.png", "reports")


def test_gcs_default_namespace_must_be_mapped() -> None:
    with pytest.raises(ValueError, match="default_namespace"):
        GCSAssetPublisher(
            bucket="assets",
            namespaces={"reports": "reports/"},
            default_namespace="missing",
            client=FakeClient(),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bucket": ""},
        {"bucket": "assets", "upload_timeout": 0},
        {"bucket": "assets", "public_url_base": "http://cdn.example.com"},
        {"bucket": "assets", "namespaces": {"bad": "/absolute"}},
        {"bucket": "assets", "namespaces": {"bad": "a/../b"}},
        {"bucket": "assets", "namespaces": {" bad": "safe"}},
    ],
)
def test_gcs_configuration_validation(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        GCSAssetPublisher(client=FakeClient(), **kwargs)


def test_gcs_rejects_client_with_credentials_or_project() -> None:
    with pytest.raises(ValueError, match="client cannot be combined"):
        GCSAssetPublisher(bucket="assets", client=FakeClient(), credentials=object())


def test_gcs_default_client_factory_and_root_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()

    class StorageModule:
        @staticmethod
        def Client(*, project: str | None, credentials: object) -> FakeClient:
            assert project == "project-1"
            assert credentials == "credentials"
            return client

    monkeypatch.setattr(gcs, "_load_storage", lambda: StorageModule)
    publisher = GCSAssetPublisher(
        bucket="assets",
        project="project-1",
        credentials="credentials",
    )

    name = publisher._object_name("image.png", None)
    assert "/" not in name


def test_gcs_rejects_invalid_direct_filename() -> None:
    publisher = GCSAssetPublisher(bucket="assets", client=FakeClient())

    with pytest.raises(AssetPublishError, match="basename"):
        publisher._object_name("nested/image.png", None)


def test_gcs_optional_dependency_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_storage() -> Any:
        raise ImportError(
            "GCSAssetPublisher requires the optional dependency; "
            'install "chattice[gcs]"'
        )

    monkeypatch.setattr(gcs, "_load_storage", missing_storage)

    with pytest.raises(ImportError, match=r"chattice\[gcs\]"):
        GCSAssetPublisher(bucket="assets")
