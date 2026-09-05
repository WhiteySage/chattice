"""Curated findDirectMessage wrapper: explicit identity, timeout, surfaced errors."""

from __future__ import annotations

from typing import Any, cast

import pytest
from google.api_core import exceptions as api_core_exceptions
from google.apps.chat_v1.types import Space
from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot
from chattice.client.errors import (
    ChatAPIError,
    ChatInvalidArgumentError,
    ChatNotFoundError,
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


class _RecordingChatClient:
    """Records find_direct_message calls; no network."""

    def __init__(self, *, credentials: object = None, transport: object = None) -> None:
        self.credentials = credentials
        self.transport = transport
        self.calls: list[tuple[object, object]] = []

    async def find_direct_message(
        self, request: object = None, **kwargs: object
    ) -> Space:
        self.calls.append((request, kwargs.get("timeout")))
        return Space(name="spaces/DM-1")

    async def create_message(self, request: object, **_: object) -> None:
        del request


def _user_bot() -> Bot:
    return Bot(
        app_credentials_provider=_CountingProvider(_app_creds()),
        user_credentials_provider=_CountingProvider(_user_creds()),
    )


async def test_canonical_user_name_passed_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _RecordingChatClient
    )
    bot = _user_bot()

    space = await bot.user.spaces.find_direct_message("users/123456789")

    assert space.name == "spaces/DM-1"
    user_client = cast(Any, bot._user_client)
    request, timeout = user_client.calls[0]
    assert request == {"name": "users/123456789"}
    assert timeout is None


async def test_email_and_bare_id_are_canonicalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _RecordingChatClient
    )
    bot = _user_bot()

    await bot.user.spaces.find_direct_message("hr@example.com")
    await bot.user.spaces.find_direct_message("123456789")

    user_client = cast(Any, bot._user_client)
    assert user_client.calls[0][0] == {"name": "users/hr@example.com"}
    assert user_client.calls[1][0] == {"name": "users/123456789"}


async def test_timeout_is_passed_to_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _RecordingChatClient
    )
    bot = _user_bot()

    await bot.user.spaces.find_direct_message("users/1", timeout=5.0)

    user_client = cast(Any, bot._user_client)
    assert user_client.calls[0][1] == 5.0


async def test_identity_is_explicit_and_never_implicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _RecordingChatClient
    )
    bot = _user_bot()

    await bot.app.spaces.find_direct_message("users/1")
    await bot.user.spaces.find_direct_message("users/2")

    app_client = cast(Any, bot._client)
    user_client = cast(Any, bot._user_client)
    assert app_client is not user_client
    assert app_client.calls == [({"name": "users/1"}, None)]
    assert user_client.calls == [({"name": "users/2"}, None)]


class _DenyingChatClient(_RecordingChatClient):
    def __init__(self, error: Exception, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._error = error

    async def find_direct_message(self, request: object = None, **_: object) -> Space:
        raise self._error


def _permission_denied_client(**kwargs: object) -> _DenyingChatClient:
    error = api_core_exceptions.PermissionDenied("denied")  # type: ignore[no-untyped-call]
    return _DenyingChatClient(error, **kwargs)


def _invalid_argument_client(**kwargs: object) -> _DenyingChatClient:
    error = api_core_exceptions.InvalidArgument("bad")  # type: ignore[no-untyped-call]
    return _DenyingChatClient(error, **kwargs)


def _not_found_client(**kwargs: object) -> _DenyingChatClient:
    error = api_core_exceptions.NotFound("no dm")  # type: ignore[no-untyped-call]
    return _DenyingChatClient(error, **kwargs)


async def test_permission_denied_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _permission_denied_client
    )
    bot = _user_bot()

    with pytest.raises(ChatPermissionDeniedError):
        await bot.user.spaces.find_direct_message("users/1")


async def test_invalid_argument_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _invalid_argument_client
    )
    bot = _user_bot()

    with pytest.raises(ChatInvalidArgumentError):
        await bot.user.spaces.find_direct_message("users/1")


async def test_not_found_raises_chat_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _not_found_client)
    bot = _user_bot()

    with pytest.raises(ChatNotFoundError):
        await bot.user.spaces.find_direct_message("users/1")


async def test_malformed_user_fails_closed_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chattice.client.bot.ChatServiceAsyncClient", _RecordingChatClient
    )
    bot = _user_bot()

    with pytest.raises(ChatAPIError):
        await bot.user.spaces.find_direct_message("bad/name/here")

    user_client = bot._user_client
    assert user_client is None  # no client was ever built


async def test_direct_message_space_uri_is_passed_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The official space_uri is the supported direct-chat link."""

    class _UriClient(_RecordingChatClient):
        async def find_direct_message(
            self, request: object = None, **_: object
        ) -> Space:
            self.calls.append((request, None))
            return Space(
                name="spaces/DM-1",
                space_uri="https://chat.google.com/space/DM-1",
            )

    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _UriClient)
    bot = _user_bot()

    space = await bot.user.spaces.find_direct_message("users/1")

    assert space.space_uri == "https://chat.google.com/space/DM-1"
