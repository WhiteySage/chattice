"""Per-call timeouts, cancellation, and no-framework-retry behavior."""

from __future__ import annotations

import asyncio

import pytest
from google.api_core import exceptions as api_core_exceptions
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.client import Bot, ChatRateLimitError
from tests.client._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _bot(transport: FakeChatTransport) -> Bot:
    return Bot(
        credentials=_creds(),
        transport=transport,
        auth_mode=AuthMode.APP,
    )


async def test_timeout_passed_to_sdk() -> None:
    transport = FakeChatTransport(credentials=_creds())
    await _bot(transport).send_message("spaces/AAA", text="x", timeout=7.5)
    assert transport.timeouts == [7.5]


async def test_default_timeout_is_none() -> None:
    transport = FakeChatTransport(credentials=_creds())
    await _bot(transport).send_message("spaces/AAA", text="x")
    assert transport.timeouts == [None]


async def test_cancellation_propagates() -> None:
    transport = FakeChatTransport(credentials=_creds())
    transport.delay = 1.0  # make create_message slow

    async def cancel_soon() -> None:
        task = asyncio.ensure_future(
            _bot(transport).send_message("spaces/AAA", text="x")
        )
        await asyncio.sleep(0.01)
        task.cancel()
        await task  # surface the CancelledError from the cancelled send

    with pytest.raises(asyncio.CancelledError):
        await cancel_soon()


async def test_rate_limit_not_retried_by_framework() -> None:
    transport = FakeChatTransport(
        credentials=_creds(),
        error=api_core_exceptions.ResourceExhausted("quota"),  # type: ignore[no-untyped-call]
    )
    with pytest.raises(ChatRateLimitError):
        await _bot(transport).send_message("spaces/AAA", text="x")
    # The framework performed exactly ONE transport call: no blind retry.
    assert len(transport.calls) == 1
