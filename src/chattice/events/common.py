"""Common interaction metadata values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DialogEventType(StrEnum):
    """Stable documented Google Chat dialog interaction types."""

    REQUEST_DIALOG = "REQUEST_DIALOG"
    SUBMIT_DIALOG = "SUBMIT_DIALOG"
    CANCEL_DIALOG = "CANCEL_DIALOG"


@dataclass(frozen=True, slots=True, kw_only=True)
class DialogMetadata:
    """Incoming dialog state without any response-building behavior."""

    type: DialogEventType | str
    is_dialog_event: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeZone:
    """Locale-independent timezone metadata supplied by Google."""

    id: str | None = None
    offset_ms: int | None = None


__all__ = ["DialogEventType", "DialogMetadata", "TimeZone"]
