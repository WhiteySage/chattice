"""Space lifecycle interaction events."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class AddedToSpaceEvent(Event):
    """The Chat app was added to a space."""

    event_type: str = field(default="added_to_space", init=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class RemovedFromSpaceEvent(Event):
    """The Chat app was removed from a space."""

    event_type: str = field(default="removed_from_space", init=False)


__all__ = ["AddedToSpaceEvent", "RemovedFromSpaceEvent"]
