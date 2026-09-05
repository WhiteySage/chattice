"""Tests for explicit paging over both iterator protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from chattice.client.paging import Pager


class _GapicStylePager:
    """Mimics a GAPIC async pager: async generator over ITEMS."""

    def __init__(self, items: list[object]) -> None:
        self._items = items

    async def __aiter__(self) -> AsyncIterator[object]:
        for item in self._items:
            yield item


class _PlainIterator:
    """Async iterator exposing __anext__ directly."""

    def __init__(self, items: list[object]) -> None:
        self._items = iter(items)

    def __aiter__(self) -> object:
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


async def test_pager_flattens_gapic_pager_items() -> None:
    async def fetch() -> object:
        return _GapicStylePager(["a", "b", "c"])

    pager: Pager[object] = Pager(fetch=fetch)
    assert [item async for item in pager] == ["a", "b", "c"]


async def test_pager_supports_plain_anext_iterators() -> None:
    async def fetch() -> object:
        return _PlainIterator([1, 2, 3])

    pager: Pager[object] = Pager(fetch=fetch)
    assert [item async for item in pager] == [1, 2, 3]


async def test_collect_limit_stops_early() -> None:
    fetched = 0

    async def fetch() -> object:
        nonlocal fetched
        fetched += 1
        return _GapicStylePager([1, 2, 3, 4])

    pager: Pager[object] = Pager(fetch=fetch)
    assert await pager.collect(limit=2) == [1, 2]
    assert fetched == 1


async def test_pager_is_reiterable() -> None:
    async def fetch() -> object:
        return _GapicStylePager([1, 2])

    pager: Pager[object] = Pager(fetch=fetch)
    assert await pager.collect() == [1, 2]
    assert await pager.collect() == [1, 2]  # fresh iteration, fresh fetch


class _FailingPager:
    """Yields items, then raises — like a GAPIC pager failing mid-stream."""

    def __init__(self, items: list[object], error: Exception) -> None:
        self._items = list(items)
        self._error = error

    async def __aiter__(self) -> AsyncIterator[object]:
        for item in self._items:
            yield item
        raise self._error


async def test_empty_pager_collects_nothing() -> None:
    async def fetch() -> object:
        return _GapicStylePager([])

    assert await Pager(fetch=fetch).collect() == []


async def test_page_two_failure_is_propagated() -> None:
    """A failing later page must not hide partial iteration."""

    async def fetch() -> object:
        return _FailingPager(["a", "b"], RuntimeError("page 2 boom"))

    pager: Pager[object] = Pager(fetch=fetch)
    iterator = pager.__aiter__()
    assert await iterator.__anext__() == "a"
    assert await iterator.__anext__() == "b"
    try:
        await iterator.__anext__()
    except RuntimeError as exc:
        assert "page 2 boom" in str(exc)
    else:
        raise AssertionError("page 2 failure was swallowed")


async def test_cancellation_does_not_leave_hanging_tasks() -> None:
    """Cancelling iteration must cancel the underlying fetch, not hang."""
    import asyncio

    fetch_started = asyncio.Event()
    fetch_done = asyncio.Event()

    async def fetch() -> object:
        fetch_started.set()
        try:
            await asyncio.Event().wait()  # hangs until cancelled
        finally:
            fetch_done.set()
        return _GapicStylePager(["x"])

    pager: Pager[object] = Pager(fetch=fetch)
    task = asyncio.ensure_future(pager.__anext__())
    await fetch_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # The in-flight fetch was cancelled with the iterator — nothing
    # keeps running afterwards.
    assert fetch_done.is_set()


async def test_no_infinite_loop_on_repeated_next() -> None:
    """Exhausted pager keeps raising StopAsyncIteration, never loops."""
    import asyncio

    async def fetch() -> object:
        return _GapicStylePager([1])

    pager: Pager[object] = Pager(fetch=fetch)
    iterator = pager.__aiter__()
    assert await iterator.__anext__() == 1
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(iterator.__anext__(), timeout=1)
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(iterator.__anext__(), timeout=1)
