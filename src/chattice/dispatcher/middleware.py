"""Middleware registration and invocation."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping

from chattice.events import Event
from chattice.middleware import MiddlewareLike, NextHandler


class MiddlewareManager:
    """An ordered middleware registry usable as a decorator."""

    def __init__(self) -> None:
        self._items: list[MiddlewareLike] = []

    def register(self, middleware: MiddlewareLike) -> MiddlewareLike:
        if not callable(middleware):
            raise TypeError("Middleware must be callable")
        self._items.append(middleware)
        return middleware

    def __call__(self, middleware: MiddlewareLike) -> MiddlewareLike:
        return self.register(middleware)

    def __iter__(self) -> Iterator[MiddlewareLike]:
        return iter(tuple(self._items))

    def __len__(self) -> int:
        return len(self._items)


async def invoke_with_middleware(
    handler: NextHandler,
    middleware: tuple[MiddlewareLike, ...],
    event: Event,
    data: MutableMapping[str, object],
) -> object:
    """Invoke middleware in registration order around a handler."""
    current = handler
    for item in reversed(middleware):
        next_handler = current

        async def wrapped(
            wrapped_event: Event,
            wrapped_data: MutableMapping[str, object],
            *,
            _middleware: MiddlewareLike = item,
            _next: NextHandler = next_handler,
        ) -> object:
            return await _middleware(_next, wrapped_event, wrapped_data)

        current = wrapped
    return await current(event, data)


__all__ = ["MiddlewareManager"]
