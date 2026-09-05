"""Forward-compatible unknown event."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownEvent(Event):
    """An event whose external type is not understood by the framework."""

    event_type: str = field(default="unknown", init=False)
    original_type: str = ""
