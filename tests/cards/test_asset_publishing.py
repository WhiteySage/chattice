"""Local Card Image publication and Bot resolution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.cards import Card, Image, Section
from chattice.client import Bot
from chattice.exceptions import AssetPublisherNotConfigured, AssetPublishError
from tests.client._fake_transport import FakeChatTransport


@dataclass
class RecordingPublisher:
    url: str = "https://assets.example.com/report.png"
    calls: list[dict[str, object]] = field(default_factory=list)

    async def publish(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        namespace: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "data": data,
                "filename": filename,
                "content_type": content_type,
                "namespace": namespace,
            }
        )
        return self.url


def _card(*images: Image) -> Card:
    return Card(sections=[Section(widgets=list(images))])


def _bot(
    transport: FakeChatTransport, publisher: RecordingPublisher | None = None
) -> Bot:
    credentials = AnonymousCredentials()  # type: ignore[no-untyped-call]
    return Bot(
        credentials=credentials,
        transport=transport,
        asset_publisher=publisher,
    )


def test_image_from_url_preserves_existing_constructor() -> None:
    direct = Image("https://assets.example.com/static.png", alt_text="Static")
    factory = Image.from_url("https://assets.example.com/static.png", alt_text="Static")

    assert direct == factory
    assert direct.image_url == "https://assets.example.com/static.png"


def test_image_from_bytes_snapshots_mutable_buffers_and_infers_type() -> None:
    source = bytearray(b"png-before")
    image = Image.from_bytes(
        source,
        filename="report.png",
        namespace="reports",
    )
    source[:] = b"png-after"

    local = image._local_source
    assert local is not None
    assert local.data == b"png-before"  # type: ignore[union-attr]
    assert local.content_type == "image/png"


def test_image_from_path_is_lazy(tmp_path: Path) -> None:
    missing = tmp_path / "created-later.png"
    image = Image.from_path(missing, namespace="reports")

    assert image.image_url is None
    assert image._local_source is not None


def test_local_image_validates_empty_data_filename_namespace_and_url() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        Image.from_bytes(b"", filename="image.png")
    with pytest.raises(ValueError, match="basename"):
        Image.from_bytes(b"image", filename="nested/image.png")
    with pytest.raises(ValueError, match="logical name"):
        Image.from_bytes(b"image", filename="image.png", namespace="a/b")
    with pytest.raises(ValueError, match="HTTPS URL"):
        Image(None)


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("report.gif", None), ("report", None), ("report.png", "image/webp")],
)
def test_local_image_rejects_unsupported_or_unknown_types(
    filename: str, content_type: str | None
) -> None:
    with pytest.raises(ValueError, match=r"PNG or JPEG|could not be inferred"):
        Image.from_bytes(
            b"image",
            filename=filename,
            content_type=content_type,
        )


async def test_send_resolves_bytes_and_preserves_original_card() -> None:
    transport = FakeChatTransport()
    publisher = RecordingPublisher()
    source = Image.from_bytes(
        b"report-bytes",
        filename="report.png",
        namespace="reports",
        alt_text="Report",
    )
    card = _card(source)

    await _bot(transport, publisher).app.messages.create("spaces/AAA", card=card)

    assert publisher.calls == [
        {
            "data": b"report-bytes",
            "filename": "report.png",
            "content_type": "image/png",
            "namespace": "reports",
        }
    ]
    sent = transport.requests[-1].message.cards_v2[0].card
    assert sent.sections[0].widgets[0].image.image_url == publisher.url
    assert sent.sections[0].widgets[0].image.alt_text == "Report"
    assert source.image_url is None
    assert card.sections[0].widgets[0] is source


async def test_send_preloads_paths_and_resolves_multiple_images(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    publisher = RecordingPublisher()
    transport = FakeChatTransport()

    await _bot(transport, publisher).app.messages.create(
        "spaces/AAA",
        card=_card(Image.from_path(first), Image.from_path(second)),
    )

    assert [call["data"] for call in publisher.calls] == [b"first", b"second"]
    assert [call["content_type"] for call in publisher.calls] == [
        "image/png",
        "image/jpeg",
    ]


async def test_update_message_resolves_local_image() -> None:
    transport = FakeChatTransport()
    sent = await _bot(transport).app.messages.create("spaces/AAA", text="before")
    publisher = RecordingPublisher()

    await _bot(transport, publisher).app.messages.update(
        sent.name,
        card=_card(Image.from_bytes(b"new", filename="new.png")),
    )

    updated = transport.updates[-1].message.cards_v2[0].card
    assert updated.sections[0].widgets[0].image.image_url == publisher.url


async def test_url_image_never_calls_publisher() -> None:
    transport = FakeChatTransport()
    publisher = RecordingPublisher()

    await _bot(transport, publisher).app.messages.create(
        "spaces/AAA",
        card=_card(Image.from_url("https://assets.example.com/static.png")),
    )

    assert publisher.calls == []


async def test_local_image_without_publisher_fails_before_credentials() -> None:
    provider_calls = 0

    def credentials_provider() -> AnonymousCredentials:
        nonlocal provider_calls
        provider_calls += 1
        return AnonymousCredentials()  # type: ignore[no-untyped-call]

    bot = Bot(
        credentials_provider=credentials_provider,
        transport=FakeChatTransport(),
    )

    with pytest.raises(
        AssetPublisherNotConfigured, match=r"Configure Bot\(asset_publisher="
    ):
        await bot.app.messages.create(
            "spaces/AAA",
            card=_card(Image.from_bytes(b"image", filename="image.png")),
        )
    assert provider_calls == 0


async def test_invalid_publisher_url_fails_before_chat_request() -> None:
    transport = FakeChatTransport()
    publisher = RecordingPublisher(url="http://private.example.com/image.png")

    with pytest.raises(AssetPublishError, match="absolute HTTPS URL"):
        await _bot(transport, publisher).app.messages.create(
            "spaces/AAA",
            card=_card(Image.from_bytes(b"image", filename="image.png")),
        )
    assert transport.requests == []


async def test_non_string_and_raising_publishers_are_wrapped() -> None:
    class NonStringPublisher:
        async def publish(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            return object()

    class RaisingPublisher:
        async def publish(self, *args: object, **kwargs: object) -> str:
            del args, kwargs
            raise RuntimeError("storage secret")

    card = _card(Image.from_bytes(b"image", filename="image.png"))
    with pytest.raises(AssetPublishError, match="absolute HTTPS"):
        await Bot(
            credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
            transport=FakeChatTransport(),
            asset_publisher=NonStringPublisher(),  # type: ignore[arg-type]
        ).app.messages.create("spaces/AAA", card=card)
    with pytest.raises(AssetPublishError, match="failed to publish") as caught:
        await Bot(
            credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
            transport=FakeChatTransport(),
            asset_publisher=RaisingPublisher(),
        ).app.messages.create("spaces/AAA", card=card)
    assert isinstance(caught.value.__cause__, RuntimeError)


async def test_publisher_cancellation_is_not_wrapped() -> None:
    class CancelledPublisher:
        async def publish(self, *args: object, **kwargs: object) -> str:
            del args, kwargs
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await Bot(
            credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
            transport=FakeChatTransport(),
            asset_publisher=CancelledPublisher(),
        ).app.messages.create(
            "spaces/AAA",
            card=_card(Image.from_bytes(b"image", filename="image.png")),
        )


@pytest.mark.parametrize("kind", ["missing", "directory", "empty"])
async def test_path_read_failures_are_typed(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "image.png"
    if kind == "directory":
        path.mkdir()
    elif kind == "empty":
        path.write_bytes(b"")

    with pytest.raises(AssetPublishError, match=r"Could not read|regular file|empty"):
        await _bot(FakeChatTransport(), RecordingPublisher()).app.messages.create(
            "spaces/AAA", card=_card(Image.from_path(path))
        )


def test_bot_rejects_invalid_publisher_shape() -> None:
    with pytest.raises(TypeError, match="publish"):
        Bot(asset_publisher=object())  # type: ignore[arg-type]


def test_direct_serialization_of_local_image_fails_clearly() -> None:
    card = _card(Image.from_bytes(b"image", filename="image.png"))

    with pytest.raises(AssetPublishError, match="message resource clients"):
        card.to_proto()
