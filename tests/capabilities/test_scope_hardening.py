"""No-network OAuth-scope hardening for outbound capability preflight."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from google.auth.credentials import AnonymousCredentials, Credentials

from chattice.auth import AuthMode
from chattice.capabilities import (
    CapabilityNotSupported,
    OutboundCapabilities,
    OutboundCapability,
)
from chattice.client import Bot
from tests.client._fake_transport import FakeChatTransport

_SCOPE_PREFIX = "https://www.googleapis.com/auth/"
_CHAT_APP_SPACES = f"{_SCOPE_PREFIX}chat.app.spaces"
_CHAT_MESSAGES = f"{_SCOPE_PREFIX}chat.messages"
_CHAT_MESSAGES_CREATE = f"{_SCOPE_PREFIX}chat.messages.create"
_CHAT_MESSAGES_READONLY = f"{_SCOPE_PREFIX}chat.messages.readonly"


class _ScopedCredentials(AnonymousCredentials):
    """Local credential stand-in exposing requested and granted scopes."""

    def __init__(
        self,
        scopes: Iterable[str],
        *,
        granted_scopes: Iterable[str] | None = None,
    ) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.scopes = tuple(scopes)
        self.granted_scopes = None if granted_scopes is None else tuple(granted_scopes)


class _CountingProvider:
    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self.calls = 0

    def __call__(self) -> Credentials:
        self.calls += 1
        return self.credentials


def test_unknown_scopes_preserve_auth_mode_capabilities() -> None:
    capabilities = OutboundCapabilities.resolve(AuthMode.USER)
    assert OutboundCapability.MESSAGE_CREATE in capabilities
    assert OutboundCapability.MESSAGE_UPDATE in capabilities


def test_known_empty_scopes_fail_closed() -> None:
    capabilities = OutboundCapabilities.resolve(AuthMode.USER, scopes=())
    assert OutboundCapability.MESSAGE_CREATE not in capabilities
    assert OutboundCapability.MESSAGE_UPDATE not in capabilities


def test_broader_user_scope_satisfies_message_create_any_of_rule() -> None:
    granted_scopes = {_CHAT_MESSAGES}
    assert _CHAT_MESSAGES_CREATE not in granted_scopes
    capabilities = OutboundCapabilities.resolve(
        AuthMode.USER,
        scopes=granted_scopes,
    )
    assert OutboundCapability.MESSAGE_CREATE in capabilities
    assert OutboundCapability.MESSAGE_UPDATE in capabilities


def test_app_admin_scope_does_not_imply_unrelated_capability_or_approval() -> None:
    capabilities = OutboundCapabilities.resolve(
        AuthMode.APP,
        scopes={_CHAT_APP_SPACES},
    )
    assert OutboundCapability.MESSAGE_CREATE not in capabilities
    assert OutboundCapability.MESSAGE_UPDATE not in capabilities


async def test_readonly_user_credentials_reject_create_before_transport() -> None:
    credentials = _ScopedCredentials({_CHAT_MESSAGES_READONLY})
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(credentials=credentials, transport=transport, auth_mode=AuthMode.USER)

    with pytest.raises(CapabilityNotSupported, match="MESSAGE_CREATE"):
        await bot.send_message("spaces/AAA", text="x")

    assert transport.requests == []


async def test_granted_scopes_override_broader_requested_scopes() -> None:
    credentials = _ScopedCredentials(
        {_CHAT_MESSAGES},
        granted_scopes={_CHAT_MESSAGES_READONLY},
    )
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(credentials=credentials, transport=transport, auth_mode=AuthMode.USER)

    with pytest.raises(CapabilityNotSupported, match="MESSAGE_CREATE"):
        await bot.send_message("spaces/AAA", text="x")

    assert transport.requests == []


async def test_unknown_credential_scopes_do_not_false_reject() -> None:
    credentials = AnonymousCredentials()  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(credentials=credentials, transport=transport, auth_mode=AuthMode.USER)

    await bot.send_message("spaces/AAA", text="x")

    assert len(transport.requests) == 1


async def test_broader_user_credential_scope_reaches_transport() -> None:
    credentials = _ScopedCredentials({_CHAT_MESSAGES})
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(credentials=credentials, transport=transport, auth_mode=AuthMode.USER)

    await bot.send_message("spaces/AAA", text="x")

    assert len(transport.requests) == 1


def test_capability_inspection_does_not_resolve_explicit_mode_provider() -> None:
    provider = _CountingProvider(_ScopedCredentials({_CHAT_MESSAGES_READONLY}))
    bot = Bot(credentials_provider=provider, auth_mode=AuthMode.USER)

    capabilities = bot.capabilities

    assert capabilities is not None
    assert OutboundCapability.MESSAGE_CREATE in capabilities
    assert provider.calls == 0


async def test_lazy_provider_resolution_feeds_scopes_into_preflight() -> None:
    credentials = _ScopedCredentials({_CHAT_MESSAGES_READONLY})
    provider = _CountingProvider(credentials)
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(
        credentials_provider=provider,
        transport=transport,
        auth_mode=AuthMode.USER,
    )

    with pytest.raises(CapabilityNotSupported, match="MESSAGE_CREATE"):
        await bot.send_message("spaces/AAA", text="x")

    capabilities = bot.capabilities
    assert capabilities is not None
    assert OutboundCapability.MESSAGE_CREATE not in capabilities
    assert provider.calls == 1
    assert transport.requests == []
