"""SDK errors become ChatAPIError subtypes with chaining."""

from __future__ import annotations

from google.api_core import exceptions as api_core_exceptions
from google.auth.credentials import AnonymousCredentials

from chattice.client import (
    Bot,
    ChatAPIError,
    ChatPermissionDeniedError,
    ChatRateLimitError,
    ChatServiceUnavailableError,
)

from ._fake_transport import FakeChatTransport


def _bot_with_error(error: Exception) -> Bot:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    return Bot(
        credentials=creds,
        transport=FakeChatTransport(error=error, credentials=creds),
    )


async def _assert_maps(
    error: api_core_exceptions.GoogleAPICallError, expected: type[ChatAPIError]
) -> None:
    bot = _bot_with_error(error)
    try:
        await bot.send_message("spaces/AAA", text="x")
    except expected as wrapped:
        assert wrapped.__cause__ is error
        assert wrapped.code == error.code
    else:  # pragma: no cover
        raise AssertionError(f"expected {expected.__name__}")


async def test_permission_denied_maps() -> None:
    await _assert_maps(
        api_core_exceptions.PermissionDenied(  # type: ignore[no-untyped-call]
            "You are not permitted to use this app"
        ),
        ChatPermissionDeniedError,
    )


async def test_resource_exhausted_maps() -> None:
    await _assert_maps(
        api_core_exceptions.ResourceExhausted("quota"),  # type: ignore[no-untyped-call]
        ChatRateLimitError,
    )


async def test_too_many_requests_maps() -> None:
    await _assert_maps(
        api_core_exceptions.TooManyRequests("429"),  # type: ignore[no-untyped-call]
        ChatRateLimitError,
    )


async def test_service_unavailable_maps() -> None:
    await _assert_maps(
        api_core_exceptions.ServiceUnavailable("down"),  # type: ignore[no-untyped-call]
        ChatServiceUnavailableError,
    )
