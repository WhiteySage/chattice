"""Outgoing Chat API error abstraction.

SDK errors (google.api_core.exceptions.GoogleAPICallError) are wrapped into
framework exceptions; the original error is always preserved as __cause__ and
its .code/.details remain reachable.
"""

from __future__ import annotations

from google.api_core import exceptions as api_core_exceptions


class ChatAPIError(Exception):
    """An outgoing Chat API call failed.

    SDK failures preserve the original error as __cause__ (raise with
    ``from error``); framework-raised errors (e.g. missing credentials)
    have no SDK cause, and the properties below return None for them.
    """

    @property
    def cause(self) -> api_core_exceptions.GoogleAPICallError | None:
        """The original SDK error, or None for framework-raised errors."""
        cause = self.__cause__
        if isinstance(cause, api_core_exceptions.GoogleAPICallError):
            return cause
        return None

    @property
    def code(self) -> int | None:
        """HTTP status code carried by the SDK error, or None."""
        cause = self.cause
        return cause.code if cause is not None else None

    @property
    def details(self) -> object:
        """Error details carried by the SDK error, or None."""
        cause = self.cause
        return cause.details if cause is not None else None


class ChatNotFoundError(ChatAPIError):
    """The target resource does not exist."""


class ChatPermissionDeniedError(ChatAPIError):
    """The app lacks permission (e.g. not a member of the space)."""


class ChatInvalidArgumentError(ChatAPIError):
    """The request was rejected by validation."""


class ChatRateLimitError(ChatAPIError):
    """Quota exhausted or 429 response; retry only per the app's policy."""


class ChatServiceUnavailableError(ChatAPIError):
    """Transient Chat API unavailability (5xx).

    ``DeadlineExceeded`` (a ``GatewayTimeout`` subclass) also maps here.
    """


class ChatUnauthenticatedError(ChatAPIError):
    """The credentials were rejected."""


_WRAPPERS: tuple[
    tuple[tuple[type[api_core_exceptions.GoogleAPICallError], ...], type[ChatAPIError]],
    ...,
] = (
    ((api_core_exceptions.NotFound,), ChatNotFoundError),
    (
        (api_core_exceptions.PermissionDenied, api_core_exceptions.Forbidden),
        ChatPermissionDeniedError,
    ),
    ((api_core_exceptions.InvalidArgument,), ChatInvalidArgumentError),
    (
        (
            api_core_exceptions.ResourceExhausted,
            api_core_exceptions.TooManyRequests,
        ),
        ChatRateLimitError,
    ),
    (
        (
            api_core_exceptions.ServiceUnavailable,
            api_core_exceptions.InternalServerError,
            api_core_exceptions.BadGateway,
            api_core_exceptions.GatewayTimeout,
        ),
        ChatServiceUnavailableError,
    ),
    (
        (api_core_exceptions.Unauthenticated, api_core_exceptions.Unauthorized),
        ChatUnauthenticatedError,
    ),
)


def wrap_api_error(error: api_core_exceptions.GoogleAPICallError) -> ChatAPIError:
    """Map an SDK error to its framework subtype (raise the result with 'from')."""
    for error_types, wrapper in _WRAPPERS:
        if isinstance(error, error_types):
            return wrapper(str(error.message))
    return ChatAPIError(str(error.message))


__all__ = [
    "ChatAPIError",
    "ChatInvalidArgumentError",
    "ChatNotFoundError",
    "ChatPermissionDeniedError",
    "ChatRateLimitError",
    "ChatServiceUnavailableError",
    "ChatUnauthenticatedError",
    "wrap_api_error",
]
