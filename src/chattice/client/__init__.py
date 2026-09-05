"""High-level async Chat API client."""

from .bot import Bot, RawClients
from .credentials import CredentialsProvider
from .errors import (
    ChatAlreadyExistsError,
    ChatAPIError,
    ChatInvalidArgumentError,
    ChatNotFoundError,
    ChatPermissionDeniedError,
    ChatRateLimitError,
    ChatServiceUnavailableError,
    ChatUnauthenticatedError,
    wrap_api_error,
)

__all__ = [
    "Bot",
    "ChatAPIError",
    "ChatAlreadyExistsError",
    "ChatInvalidArgumentError",
    "ChatNotFoundError",
    "ChatPermissionDeniedError",
    "ChatRateLimitError",
    "ChatServiceUnavailableError",
    "ChatUnauthenticatedError",
    "CredentialsProvider",
    "RawClients",
    "wrap_api_error",
]
