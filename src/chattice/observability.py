"""Extension hooks for observability (application-owned integrations).

The framework ships NO OTel dependency; applications implement these hooks
and bridge to their tracer of choice (see docs/architecture/observability.md).
"""

from __future__ import annotations

from typing import Protocol

__all__ = ["ObservabilityHooks"]


class ObservabilityHooks(Protocol):
    """Called around each feed_update routing pass."""

    async def before_event(self, event: object, data: dict[str, object]) -> None: ...

    async def after_event(
        self,
        event: object,
        data: dict[str, object],
        result: object,
        error: BaseException | None,
    ) -> None: ...
