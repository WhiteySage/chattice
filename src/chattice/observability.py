"""Extension hooks for observability (application-owned integrations).

The framework ships NO OTel dependency; applications implement these hooks
and bridge to their tracer of choice (see docs/architecture/observability.md).

The optional hooks (everything after ``after_event``) are no-ops in the
protocol: an implementation may provide any subset without breaking the
structural contract. Hooks receive the original event and dispatch context,
including access to raw payloads. Applications choose which fields to export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__ = ["ObservabilityHooks", "RuntimeDiagnostics"]


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    """Configurable thresholds for runtime diagnostics.

    ``None`` disables the corresponding warning.
    """

    slow_handler_ms: float | None = 1000.0
    delayed_event_ms: float | None = 5000.0


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

    # ---- optional hooks (no-ops in the protocol) ----

    async def before_handler(
        self, event: object, data: dict[str, object], handler: str
    ) -> None:
        """Called before the selected handler invokes; ``handler`` is the
        qualified callback name."""

    async def after_handler(
        self, event: object, data: dict[str, object], handler: str, result: object
    ) -> None:
        """Called after the selected handler returns."""

    async def before_outbound(self, event: object, operation: str) -> None:
        """Called before an outbound Google answer (send/update)."""

    async def after_outbound(self, event: object, operation: str) -> None:
        """Called after an outbound Google answer completes."""

    async def delivery_acked(self, message_id: str, event: object) -> None:
        """Called after a Pub/Sub delivery is ACKed."""

    async def delivery_nacked(self, message_id: str, event: object) -> None:
        """Called after a Pub/Sub delivery is NACKed."""
