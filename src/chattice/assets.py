"""Storage-agnostic publication contract for local Card assets."""

from __future__ import annotations

from typing import Protocol


class AssetPublisher(Protocol):
    """Publish bytes and return an absolute HTTPS URL for a Card Image."""

    async def publish(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str,
        namespace: str | None = None,
    ) -> str:
        """Publish one immutable byte snapshot."""
        ...


__all__ = ["AssetPublisher"]
