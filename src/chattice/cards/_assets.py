"""Resolve lazy local Card Images without mutating facade objects."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

from chattice.assets import AssetPublisher
from chattice.exceptions import AssetPublisherNotConfigured, AssetPublishError

from .card import Card, Section
from .widgets import Image, _BytesImageSource, _PathImageSource


def _local_images(card: Card) -> list[tuple[int, int, Image]]:
    images: list[tuple[int, int, Image]] = []
    for section_index, section in enumerate(card.sections):
        for widget_index, widget in enumerate(section.widgets):
            if isinstance(widget, Image) and widget._local_source is not None:
                images.append((section_index, widget_index, widget))
    return images


def validate_card_assets(card: Card | None, publisher: AssetPublisher | None) -> None:
    """Fail locally when a Card needs an unavailable publisher."""
    if card is not None and publisher is None and _local_images(card):
        raise AssetPublisherNotConfigured(
            "Local card images require an AssetPublisher. Configure "
            "Bot(asset_publisher=...) or use Image.from_url()."
        )


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AssetPublishError(
                f"Local Card image path must be a regular file: {path}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as file:
            data = file.read()
    finally:
        os.close(descriptor)
    if not data:
        raise AssetPublishError(f"Local Card image file is empty: {path}")
    return data


async def _source_bytes(image: Image) -> bytes:
    source = image._local_source
    if isinstance(source, _BytesImageSource):
        return source.data
    if isinstance(source, _PathImageSource):
        try:
            return await asyncio.to_thread(_read_regular_file, source.path)
        except asyncio.CancelledError:
            raise
        except AssetPublishError:
            raise
        except OSError as error:
            raise AssetPublishError(
                f"Could not read local Card image {source.path}: {error.strerror}"
            ) from error
    raise AssetPublishError("Local Card image has an invalid source")


async def resolve_card_assets(card: Card, publisher: AssetPublisher | None) -> Card:
    """Publish local Images and return a resolved immutable Card copy."""
    local_images = _local_images(card)
    if not local_images:
        return card
    validate_card_assets(card, publisher)
    assert publisher is not None

    prepared: list[tuple[int, int, Image, bytes]] = []
    for section_index, widget_index, image in local_images:
        prepared.append(
            (section_index, widget_index, image, await _source_bytes(image))
        )

    replacements: dict[tuple[int, int], Image] = {}
    for section_index, widget_index, image, data in prepared:
        source = image._local_source
        assert source is not None
        try:
            image_url = await publisher.publish(
                data,
                filename=source.filename,
                content_type=source.content_type,
                namespace=source.namespace,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise AssetPublishError(
                f"AssetPublisher failed to publish {source.filename!r}"
            ) from error
        if not isinstance(image_url, str):
            raise AssetPublishError(
                "AssetPublisher.publish() must return an absolute HTTPS URL"
            )
        try:
            resolved = Image.from_url(
                image_url,
                alt_text=image.alt_text,
                on_click=image.on_click,
            )
        except ValueError as error:
            raise AssetPublishError(
                "AssetPublisher.publish() must return an absolute HTTPS URL"
            ) from error
        replacements[(section_index, widget_index)] = resolved

    sections: list[Section] = []
    for section_index, section in enumerate(card.sections):
        widgets = [
            replacements.get((section_index, widget_index), widget)
            for widget_index, widget in enumerate(section.widgets)
        ]
        sections.append(Section(header=section.header, widgets=widgets))
    return Card(header=card.header, sections=sections, name=card.name)


__all__ = ["resolve_card_assets", "validate_card_assets"]
