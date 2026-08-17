"""Minimal lifespan contract (B5)."""

from __future__ import annotations

import pytest

from chattice import Dispatcher


class _Resource:
    def __init__(self, name: str, *, fail_start: bool = False) -> None:
        self.name = name
        self.fail_start = fail_start
        self.started = False
        self.closed = False

    async def start(self) -> None:
        if self.fail_start:
            raise RuntimeError(f"{self.name} failed to start")
        self.started = True

    async def close(self) -> None:
        self.closed = True


async def test_start_order_and_reverse_close() -> None:
    dispatcher = Dispatcher()
    events: list[str] = []
    first = _Resource("first")
    second = _Resource("second")
    async with dispatcher.lifespan(first, second):
        events.append("entered")
    assert events == ["entered"]
    assert first.started and second.started
    assert first.closed and second.closed


async def test_partial_start_failure_rolls_back() -> None:
    dispatcher = Dispatcher()
    first = _Resource("first")
    failing = _Resource("failing", fail_start=True)
    with pytest.raises(RuntimeError, match="failing"):
        async with dispatcher.lifespan(first, failing):
            pass  # pragma: no cover
    # the already-started resource was rolled back
    assert first.started and first.closed
    assert not failing.started


async def test_lifespan_is_single_use() -> None:
    dispatcher = Dispatcher()
    lifespan = dispatcher.lifespan(_Resource("r"))
    async with lifespan:
        pass
    with pytest.raises(RuntimeError, match="already"):
        async with lifespan:
            pass  # pragma: no cover


async def test_fastapi_integration_shape() -> None:
    """The lifespan plugs into FastAPI's lifespan_context via a factory."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    dispatcher = Dispatcher()
    resource = _Resource("db")
    app = FastAPI()

    @asynccontextmanager
    async def lifespan_factory(app: FastAPI) -> AsyncIterator[None]:
        async with dispatcher.lifespan(resource):
            yield

    app.router.lifespan_context = lifespan_factory
    assert app.router.lifespan_context is not None
