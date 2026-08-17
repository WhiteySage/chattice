"""Framework-neutral incoming HTTP request snapshot."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from chattice.adapters.google_chat.exceptions import InvalidInteractionPayload


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class IncomingRequest:
    """Immutable snapshot of an inbound interaction HTTP request."""

    method: str
    path: str
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    received_at: datetime = field(default_factory=_utcnow)

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup."""
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None

    def json(self) -> Mapping[str, object]:
        """Decode the body as a JSON object (lazy, one call per request)."""
        try:
            decoded = json.loads(self.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InvalidInteractionPayload("Request body is not valid JSON") from error
        if not isinstance(decoded, Mapping):
            raise InvalidInteractionPayload("Request body must be a JSON object")
        return decoded


__all__ = ["IncomingRequest"]
