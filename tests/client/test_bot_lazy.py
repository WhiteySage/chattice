"""Bot construction and lazy client creation."""

from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.capabilities import CapabilityNotSupported
from chattice.client import Bot, ChatAPIError

from ._fake_transport import FakeChatTransport


async def test_bot_without_credentials_raises_on_first_call() -> None:
    """Zero-credential Bots fail closed BEFORE any client build or I/O."""
    bot = Bot()
    with pytest.raises(CapabilityNotSupported, match="no credentials"):
        await bot.app.messages.get("spaces/A/messages/1")


async def test_raw_app_without_credentials_raises() -> None:
    bot = Bot()
    try:
        _ = await bot.raw.app()
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError")


async def test_client_is_created_once() -> None:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    bot = Bot(credentials=creds, transport=FakeChatTransport(credentials=creds))
    client = await bot.raw.app()
    assert await bot.raw.app() is client
