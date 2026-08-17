"""Object-oriented facade for Google Chat interaction parsing."""

from __future__ import annotations

from collections.abc import Mapping

from chattice.events import Event

from .parser import parse_interaction


class GoogleInteractionAdapter:
    """Stateless pure adapter reusable by later transports."""

    def parse(self, payload: Mapping[str, object]) -> Event:
        """Parse one decoded JSON mapping."""
        return parse_interaction(payload)


__all__ = ["GoogleInteractionAdapter"]
