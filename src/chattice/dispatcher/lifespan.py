"""Minimal application lifespan: ordered startup, reverse shutdown.

One contract, no plugin framework. Resources are started in registration
order; on partial-start failure, already-started resources are closed in
reverse order and the error re-raises; shutdown closes everything in
reverse order regardless of handler errors. The Lifespan object is an
async context manager, so it plugs into FastAPI directly:

    app.router.lifespan_context = dispatcher.lifespan(client, db)

(``Bot`` participates through its own async context manager /
``close()``; wrap it in a LifespanResource or nest the managers.)
"""

from __future__ import annotations

import logging
from typing import Protocol

__all__ = ["Lifespan", "LifespanResource"]

logger = logging.getLogger("chattice.lifespan")


class LifespanResource(Protocol):
    """A resource with ordered async startup and shutdown."""

    async def start(self) -> None: ...

    async def close(self) -> None: ...


class Lifespan:
    """Ordered startup / reverse-order shutdown over async resources."""

    def __init__(self, *resources: LifespanResource) -> None:
        self._resources = tuple(resources)
        self._started: list[LifespanResource] = []
        self._closed = False

    async def __aenter__(self) -> Lifespan:
        if self._closed:
            raise RuntimeError("This lifespan has already been used")
        started = self._started
        try:
            for resource in self._resources:
                await resource.start()
                started.append(resource)
        except BaseException:
            # Partial start: roll back in reverse order, then re-raise.
            for resource in reversed(started):
                try:
                    await resource.close()
                except BaseException as close_error:  # pragma: no cover - logged
                    logger.error(
                        "lifespan rollback failed: resource=%s error=%s",
                        type(resource).__name__,
                        type(close_error).__name__,
                    )
            started.clear()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        # Attempt EVERY closer in reverse order; collect the first close
        # failure and surface it only after cleanup completes.
        close_errors: list[BaseException] = []
        for resource in reversed(self._started):
            try:
                await resource.close()
            except BaseException as close_error:
                logger.error(
                    "lifespan shutdown failed: resource=%s error=%s",
                    type(resource).__name__,
                    type(close_error).__name__,
                )
                close_errors.append(close_error)
        self._started.clear()
        self._closed = True
        if close_errors and exc_type is None:
            # A clean exit that hits a close failure must surface.
            raise close_errors[0]
