"""Bot auth integration: provider priority, classification, guards before transport."""

from __future__ import annotations

from typing import cast

import pytest
from google.auth.credentials import AnonymousCredentials, Credentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.client import Bot
from tests.auth.test_providers import _FlaggedCredentials
from tests.client._fake_transport import FakeChatTransport


class _CountingProvider:
    def __init__(self, credentials: Credentials) -> None:
        self._credentials = credentials
        self.calls = 0

    def __call__(self) -> Credentials:
        self.calls += 1
        return self._credentials


class _FakeAsyncClient:
    """Records the credentials passed at construction; no network.

    Bot builds its SDK client lazily from provider/credentials, so these
    tests stub ChatServiceAsyncClient to observe the wiring without a
    real gRPC channel.
    """

    def __init__(self, *, credentials: object = None, transport: object = None) -> None:
        self.credentials = credentials
        self.transport = transport

    async def create_message(self, request: object, **_: object) -> None:
        del request


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _service_account_credentials() -> Credentials:
    """Real service-account credentials with a valid ephemeral RSA key.

    google-auth validates the RSA PEM on load (a truncated dummy key is
    rejected), so generate a genuine key with cryptography (dev dep).
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.oauth2 import service_account

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    loader = service_account.Credentials.from_service_account_info
    info = {
        "type": "service_account",
        "project_id": "p",
        "private_key_id": "k",
        "private_key": private_key,
        "client_email": "a@p.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return loader(info, scopes=["https://www.googleapis.com/auth/chat.bot"])  # type: ignore[no-untyped-call, no-any-return]


async def test_provider_called_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _CountingProvider(_creds())
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = Bot(credentials_provider=provider, auth_mode=AuthMode.APP)
    await bot.send_message("spaces/AAA", text="x")
    await bot.send_message("spaces/AAA", text="y")
    assert provider.calls == 1


async def test_provider_wins_over_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _CountingProvider(_creds())
    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _FakeAsyncClient)
    bot = Bot(
        credentials=_creds(),
        credentials_provider=provider,
        auth_mode=AuthMode.APP,
    )
    await bot.send_message("spaces/AAA", text="x")
    assert provider.calls == 1
    client = cast(_FakeAsyncClient, bot.raw_client)
    assert client.credentials is provider._credentials  # provider won over credentials=


def test_auto_classification_service_account() -> None:
    credentials = _service_account_credentials()
    bot = Bot(credentials=credentials)
    assert bot.auth_mode is AuthMode.APP
    assert bot.capabilities is not None


async def test_unsupported_mode_fails_before_network() -> None:
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(
        credentials=_creds(),
        transport=transport,
        auth_mode=AuthMode.NONE,  # NONE has no MESSAGE_CREATE
    )
    with pytest.raises(CapabilityNotSupported):
        await bot.send_message("spaces/AAA", text="x")
    assert transport.requests == []  # zero network calls


async def test_implicit_mode_provider_called_once_across_uses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth-mode classification and guards must not re-call the provider."""
    provider = _CountingProvider(_service_account_credentials())
    built: list[object] = []

    def _stub_client(
        *, credentials: object = None, transport: object = None
    ) -> _FakeAsyncClient:
        client = _FakeAsyncClient(credentials=credentials, transport=transport)
        built.append(client)
        return client

    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _stub_client)
    bot = Bot(credentials_provider=provider)  # implicit mode: classification needed
    assert bot.capabilities is not None  # triggers classification (SA -> APP)
    assert bot.capabilities is not None  # second access must stay cached
    assert provider.calls == 1


async def test_user_classification_from_refresh_token() -> None:
    """Authorized-user credentials (refresh_token, no signer) -> USER."""
    bot = Bot(credentials=_FlaggedCredentials(expired=False))
    assert bot.auth_mode is AuthMode.USER


async def test_failed_provider_raises_on_every_call() -> None:
    """Provider failures are not cached — the error re-raises each time."""

    class _FailingProvider:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self) -> Credentials:
            self.calls += 1
            raise FileNotFoundError("credentials.json")

    provider = _FailingProvider()
    bot = Bot(credentials_provider=provider)
    with pytest.raises(FileNotFoundError):
        _ = bot.capabilities
    with pytest.raises(FileNotFoundError):
        _ = bot.capabilities
    assert provider.calls == 2
