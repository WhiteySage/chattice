"""Explicit async paging over Google SDK pagers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar, cast

__all__ = ["Pager"]

T = TypeVar("T")


class Pager(Generic[T]):
    """Lazy wrapper over an SDK async pager.

    ``fetch`` returns the SDK async pager, which yields ITEMS (GAPIC
    pagers materialize items lazily across pages). ``collect(limit=...)``
    bounds total work; plain iteration never materializes more than what
    the SDK pager already holds.
    """

    def __init__(self, fetch: Callable[[], Awaitable[object]]) -> None:
        self._fetch = fetch
        self._iterator: Callable[[], Awaitable[object]] | None = None

    def __aiter__(self) -> Pager[T]:
        self._iterator = None
        return self

    async def __anext__(self) -> T:
        if self._iterator is None:
            raw = await self._fetch()
            # GAPIC pagers expose an async generator via __aiter__ (no
            # direct __anext__); plain iterators expose __anext__.
            if hasattr(raw, "__anext__"):
                self._iterator = raw.__anext__
            else:
                self._iterator = raw.__aiter__().__anext__  # type: ignore[attr-defined]
        return cast(T, await self._iterator())

    async def collect(self, limit: int | None = None) -> list[T]:
        """Materialize items, optionally bounded by ``limit``."""
        items: list[T] = []
        async for item in self:
            items.append(item)
            if limit is not None and len(items) >= limit:
                return items
        return items
