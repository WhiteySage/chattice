"""HTTP transport failures."""

from __future__ import annotations


class HTTPInteractionError(ValueError):
    """Base class for HTTP transport failures."""


class VerificationError(HTTPInteractionError):
    """Incoming request verification failed."""


class DoubleResponseError(HTTPInteractionError):
    """The synchronous response was already set for this interaction."""


__all__ = ["DoubleResponseError", "HTTPInteractionError", "VerificationError"]
