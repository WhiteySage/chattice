"""Public Google Chat interaction parsing failures."""


class GoogleInteractionError(ValueError):
    """Base class for adapter failures."""


class InvalidInteractionPayload(GoogleInteractionError):
    """The payload is structurally malformed for its declared event."""


class ConflictingEnvelopeError(GoogleInteractionError):
    """Direct and wrapped envelope data disagree."""


class UnsupportedEnvelopeError(GoogleInteractionError):
    """The mapping does not use a supported documented envelope."""


__all__ = [
    "ConflictingEnvelopeError",
    "GoogleInteractionError",
    "InvalidInteractionPayload",
    "UnsupportedEnvelopeError",
]
