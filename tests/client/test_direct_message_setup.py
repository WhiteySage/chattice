"""get_or_setup_direct_message semantics and bot.warmup."""

from __future__ import annotations

from typing import Any, cast

import pytest
from google.api_core import exceptions as api_core_exceptions
from google.apps.chat_v1.types import Space, User
from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot
from chattice.client.errors import (
    ChatAPIError,
    ChatPermissionDeniedError,
)
from tests.auth.test_bot_auth import _CountingProvider


class _AppCredentials(AnonymousCredentials):
    """Service-account stand-in: a signer classifies as APP identity."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.signer = object()


def _app_creds() -> AnonymousCredentials:
    return _AppCredentials()


class _UserCredentials(AnonymousCredentials):
    """Authorized-user stand-in: a refresh_token classifies as USER."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_token = "rt"


def _user_creds() -> AnonymousCredentials:
    return _UserCredentials()


class _SetupChatClient:
    """find_direct_message switchable; records set_up_space requests."""

    def __init__(self, *, credentials: object = None, transport: object = None) -> None:
        self.credentials = credentials
        self.transport = transport
        self.find_error: Exception | None = None
        self.setup_requests: list[tuple[object, object]] = []

    async def find_direct_message(
        self, request: object = None, **kwargs: object
    ) -> Space:
        if self.find_error is not None:
            raise self.find_error
        return Space(name="spaces/DM-existing")

    async def set_up_space(self, request: object = None, **kwargs: object) -> Space:
        self.setup_requests.append((request, kwargs.get("timeout")))
        return Space(name="spaces/DM-created")


def _user_bot() -> Bot:
    return Bot(
        app_credentials_provider=_CountingProvider(_app_creds()),
        user_credentials_provider=_CountingProvider(_user_creds()),
    )


async def test_found_dm_is_returned_without_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()

    space = await bot.user.spaces.get_or_setup_direct_message("hr@example.com")

    assert space.name == "spaces/DM-existing"
    user_client = cast(Any, bot._user_client)
    assert user_client.setup_requests == []


async def test_not_found_sets_up_direct_message_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()
    user_client = _SetupChatClient()
    user_client.find_error = api_core_exceptions.NotFound("no dm")  # type: ignore[no-untyped-call]
    bot._user_client = cast(Any, user_client)

    space = await bot.user.spaces.get_or_setup_direct_message("users/123", timeout=3.0)

    assert space.name == "spaces/DM-created"
    user_client = cast(Any, bot._user_client)
    request, timeout = user_client.setup_requests[0]
    assert timeout == 3.0
    created = request["space"]
    assert created.space_type == Space.SpaceType.DIRECT_MESSAGE
    assert request["memberships"][0].member.name == "users/123"
    assert request["memberships"][0].member.type_ == User.Type.HUMAN


async def test_permission_denied_is_not_hidden_and_no_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()
    user_client = _SetupChatClient()
    user_client.find_error = api_core_exceptions.PermissionDenied("denied")  # type: ignore[no-untyped-call]
    bot._user_client = cast(Any, user_client)

    with pytest.raises(ChatPermissionDeniedError):
        await bot.user.spaces.get_or_setup_direct_message("users/1")

    assert user_client.setup_requests == []


async def test_app_identity_cannot_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()

    with pytest.raises(ChatAPIError, match="USER"):
        await bot.app.spaces.get_or_setup_direct_message("users/1")


async def test_warmup_builds_app_client_and_resolves_provider_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _CountingProvider(_app_creds())
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = Bot(credentials_provider=provider)

    await bot.warmup()

    assert provider.calls == 1
    assert bot._client is not None


async def test_warmup_user_true_builds_both_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()

    await bot.warmup(app=True, user=True)

    assert bot._client is not None
    assert bot._user_client is not None


async def test_warmup_default_leaves_user_client_unbuilt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()

    await bot.warmup()

    assert bot._client is not None
    assert bot._user_client is None


async def test_warmup_after_close_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _SetupChatClient)
    bot = _user_bot()
    await bot.close()

    with pytest.raises(ChatAPIError, match="closed"):
        await bot.warmup()
