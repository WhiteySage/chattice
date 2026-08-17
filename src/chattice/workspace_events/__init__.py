"""Workspace Events ingress family (separate from Chat interactions)."""

from .envelope import WorkspaceEventError
from .parser import (
    WorkspaceEvent,
    WorkspaceEventType,
    parse_workspace_envelope,
    parse_workspace_event,
)
from .runtime import EventsDispatcher, EventsRouter

__all__ = [
    "EventsDispatcher",
    "EventsRouter",
    "WorkspaceEvent",
    "WorkspaceEventError",
    "WorkspaceEventType",
    "parse_workspace_envelope",
    "parse_workspace_event",
]
