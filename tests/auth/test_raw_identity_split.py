"""Explicit APP/USER raw client split."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.client import Bot
from chattice.client.errors import ChatAPIError
from tests.auth.test_bot_auth import _CountingProvider, _creds


class _FakeAsyncClient:
    """Records the credentials passed at construction; no network."""

    def __init__(self, *, credentials: object = None, transport: object = None) -> None:
        self.credentials = credentials
        self.transport = transport

    async def create_message(self, request: object, **_: object) -> None:
        del request


def _dual_bot(app_creds: AnonymousCredentials, user_creds: AnonymousCredentials) -> Bot:
    return Bot(
        app_credentials_provider=_CountingProvider(app_creds),
        user_credentials_provider=_CountingProvider(user_creds),
    )


async def test_raw_app_and_user_return_distinct_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_creds = _creds()
    user_creds = _creds()
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = _dual_bot(app_creds, user_creds)

    app_client = await bot.raw.app()
    user_client = await bot.raw.user()

    app_client = cast(Any, app_client)
    user_client = cast(Any, user_client)
    assert app_client.credentials is app_creds
    assert user_client.credentials is user_creds
    assert app_client is not user_client  # identities never mix


async def test_raw_user_without_provider_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = Bot(credentials_provider=_CountingProvider(_creds()), auth_mode=AuthMode.APP)

    with pytest.raises(CapabilityNotSupported):
        await bot.raw.user()


async def test_single_flight_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _CountingProvider(_creds())
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = Bot(credentials_provider=provider, auth_mode=AuthMode.APP)

    first, second = await asyncio.gather(bot.raw.app(), bot.raw.app())

    assert first is second
    assert provider.calls == 1


async def test_cancellation_of_waiter_does_not_kill_shared_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _CountingProvider(_creds())
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = Bot(credentials_provider=provider, auth_mode=AuthMode.APP)

    cancelled = asyncio.create_task(bot.raw.app())
    survivor = asyncio.create_task(bot.raw.app())
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    await survivor
    assert provider.calls == 1


async def test_failed_provider_is_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)

    class _FlakyProvider:
        def __init__(self, credentials: AnonymousCredentials) -> None:
            self._credentials = credentials
            self.calls = 0

        def __call__(self) -> AnonymousCredentials:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("provider down")
            return self._credentials

    provider = _FlakyProvider(_creds())
    bot = Bot(credentials_provider=provider, auth_mode=AuthMode.APP)

    with pytest.raises(RuntimeError, match="provider down"):
        await bot.raw.app()
    await bot.raw.app()

    assert provider.calls == 2


async def test_close_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    app_creds = _creds()
    user_creds = _creds()
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = _dual_bot(app_creds, user_creds)

    await bot.close()

    with pytest.raises(ChatAPIError, match="closed"):
        await bot.raw.app()
    with pytest.raises(ChatAPIError, match="closed"):
        await bot.raw.user()


async def test_scopes_do_not_select_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """raw.app() serves APP credentials even when both providers exist."""
    app_creds = _creds()
    user_creds = _creds()
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = _dual_bot(app_creds, user_creds)

    app_client = cast(_FakeAsyncClient, await bot.raw.app())

    assert app_client.credentials is app_creds
