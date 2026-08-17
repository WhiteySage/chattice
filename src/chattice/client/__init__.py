"""High-level async Chat API client."""

from .bot import Bot, MessageReplyOption
from .credentials import CredentialsProvider
from .errors import (
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
    "ChatInvalidArgumentError",
    "ChatNotFoundError",
    "ChatPermissionDeniedError",
    "ChatRateLimitError",
    "ChatServiceUnavailableError",
    "ChatUnauthenticatedError",
    "CredentialsProvider",
    "MessageReplyOption",
    "wrap_api_error",
]
