"""CloudEvent envelope helpers for Workspace Events."""

from __future__ import annotations

from datetime import datetime

REQUIRED_SPECVERSION = "1.0"
TYPE_PREFIX = "google.workspace."


class WorkspaceEventError(ValueError):
    """The CloudEvent payload is malformed for Workspace Events."""


def parse_event_time(raw: object) -> datetime | None:
    """Parse an RFC 3339 UTC timestamp; absent -> None; naive -> error."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise WorkspaceEventError("Workspace event 'time' must be an RFC 3339 string")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise WorkspaceEventError(f"Invalid 'time' value {raw!r}") from error
    if parsed.tzinfo is None:
        raise WorkspaceEventError(f"'time' value {raw!r} is not timezone-aware")
    return parsed


__all__ = [
    "REQUIRED_SPECVERSION",
    "TYPE_PREFIX",
    "WorkspaceEventError",
    "parse_event_time",
]
