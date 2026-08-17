"""Chat API client error abstraction."""

from __future__ import annotations

import pytest
from google.api_core import exceptions as api_core_exceptions

from chattice.client.errors import (
    ChatAPIError,
    ChatInvalidArgumentError,
    ChatNotFoundError,
    ChatPermissionDeniedError,
    ChatRateLimitError,
    ChatServiceUnavailableError,
    ChatUnauthenticatedError,
    wrap_api_error,
)


def _raise_wrapped(error: api_core_exceptions.GoogleAPICallError) -> None:
    raise wrap_api_error(error) from error


def _make_error(
    cls: type[api_core_exceptions.GoogleAPICallError], message: str
) -> api_core_exceptions.GoogleAPICallError:
    return cls(message)


@pytest.mark.parametrize(
    ("cls", "message", "expected"),
    [
        (api_core_exceptions.NotFound, "message not found", ChatNotFoundError),
        (api_core_exceptions.PermissionDenied, "denied", ChatPermissionDeniedError),
        (api_core_exceptions.Forbidden, "forbidden", ChatPermissionDeniedError),
        (api_core_exceptions.InvalidArgument, "bad field", ChatInvalidArgumentError),
        (api_core_exceptions.ResourceExhausted, "quota", ChatRateLimitError),
        (api_core_exceptions.TooManyRequests, "429", ChatRateLimitError),
        (api_core_exceptions.ServiceUnavailable, "down", ChatServiceUnavailableError),
        (api_core_exceptions.Unauthenticated, "bad auth", ChatUnauthenticatedError),
        (api_core_exceptions.Unauthorized, "unauthorized", ChatUnauthenticatedError),
    ],
)
def test_sdk_error_maps(
    cls: type[api_core_exceptions.GoogleAPICallError],
    message: str,
    expected: type[ChatAPIError],
) -> None:
    error = _make_error(cls, message)
    try:
        _raise_wrapped(error)
    except expected as wrapped:
        assert wrapped.__cause__ is error
        assert wrapped.code == error.code
        assert wrapped.details == error.details
    else:  # pragma: no cover
        raise AssertionError(f"expected {expected.__name__}")


def test_unknown_maps_to_base() -> None:
    error = _make_error(api_core_exceptions.Aborted, "aborted")
    try:
        _raise_wrapped(error)
    except ChatAPIError as wrapped:
        assert type(wrapped) is ChatAPIError
        assert wrapped.__cause__ is error
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError")


def test_framework_raised_error_has_no_cause() -> None:
    """ChatAPIError raised without an SDK chain (e.g. missing credentials)."""
    error = ChatAPIError("Bot has no credentials")
    assert error.cause is None
    assert error.code is None
    assert error.details is None


def test_hierarchy_subclasses_base() -> None:
    assert issubclass(ChatNotFoundError, ChatAPIError)
    assert issubclass(ChatPermissionDeniedError, ChatAPIError)
    assert issubclass(ChatInvalidArgumentError, ChatAPIError)
    assert issubclass(ChatRateLimitError, ChatAPIError)
    assert issubclass(ChatServiceUnavailableError, ChatAPIError)
    assert issubclass(ChatUnauthenticatedError, ChatAPIError)
