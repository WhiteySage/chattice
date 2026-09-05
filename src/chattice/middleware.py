"""Transport-independent dispatch middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Protocol, TypeAlias

from chattice.events import Event

NextHandler: TypeAlias = Callable[
    [Event, MutableMapping[str, object]], Awaitable[object]
]


class Middleware(Protocol):
    """Structural protocol for asynchronous dispatch middleware."""

    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object: ...


class BaseMiddleware:
    """Convenience base class for asynchronous dispatch middleware."""

    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        raise NotImplementedError


MiddlewareLike: TypeAlias = BaseMiddleware | Middleware

__all__ = ["BaseMiddleware", "Middleware", "MiddlewareLike", "NextHandler"]
