"""Error-routing event."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorEvent(Event):
    """The original event and exception presented to an error observer."""

    event_type: str = field(default="error", init=False)
    source_event: Event
    exception: Exception
