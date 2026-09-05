"""Wire an IncomingRequest into the domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event

from .request import IncomingRequest
from .response import InteractionResponse

# Documented sync response deadline:
# https://developers.google.com/workspace/chat/receive-respond-interactions
SYNC_RESPONSE_DEADLINE = timedelta(seconds=30)


@dataclass(frozen=True, slots=True, kw_only=True)
class InteractionContext:
    """HTTP transport-only request/response state available through DI.

    The normalized domain event and its response capabilities are separate DI
    values; this type deliberately does not claim to be a canonical entity or
    resource context.
    """

    request: IncomingRequest
    response: InteractionResponse
    received_at: datetime
    deadline_at: datetime

    @property
    def remaining(self) -> timedelta:
        """Time left before the documented sync response deadline."""
        return self.deadline_at - datetime.now(UTC)


class HTTPInteractionAdapter:
    """Framework-neutral adapter: HTTP request snapshot -> domain event."""

    def parse(self, request: IncomingRequest) -> Event:
        """Decode the request body and parse it into a domain event."""
        return parse_interaction(request.json())


__all__ = [
    "SYNC_RESPONSE_DEADLINE",
    "HTTPInteractionAdapter",
    "InteractionContext",
]
