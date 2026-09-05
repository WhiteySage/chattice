"""Identity-bound client roots, raw split, registry preflight (ADR-012)."""

from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported, Operation
from chattice.client import Bot
from chattice.client.config import RequestConfig
from chattice.testing import FakeChatTransport


class _AppCredentials(AnonymousCredentials):
    """Service-account stand-in: a signer classifies as APP identity."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.signer = object()


def _creds() -> AnonymousCredentials:
    return _AppCredentials()


def test_identity_roots_are_bound_without_io() -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    assert bot.app.identity is AuthMode.APP
    assert bot.user.identity is AuthMode.USER


def test_resource_roots_exist_without_io() -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    # Just building the facade must not resolve credentials.
    assert bot.app.spaces.identity is AuthMode.APP
    assert bot.user.spaces.identity is AuthMode.USER
    assert bot.app.messages.identity is AuthMode.APP
    assert bot.user.messages.identity is AuthMode.USER
    assert bot.app.memberships.identity is AuthMode.APP
    assert bot.user.memberships.identity is AuthMode.USER


async def test_preflight_operation_rejects_wrong_identity() -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    with pytest.raises(CapabilityNotSupported):
        # SPACES_LIST is APP-only; the USER identity must not pass.
        await bot._preflight_operation(Operation.SPACES_LIST, identity=AuthMode.USER)


async def test_preflight_operation_passes_app_identity() -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    # MESSAGES_CREATE is dual-auth; APP passes.
    await bot._preflight_operation(Operation.MESSAGES_CREATE, identity=AuthMode.APP)


async def test_app_resource_uses_app_client_never_user() -> None:
    class _UserCredentials(AnonymousCredentials):
        def __init__(self) -> None:
            super().__init__()  # type: ignore[no-untyped-call]
            self.refresh_token = "rt"

    bot = Bot(
        app_credentials_provider=lambda: _creds(),
        user_credentials_provider=lambda: _UserCredentials(),
        transport=FakeChatTransport(credentials=_creds()),
    )

    async def echo(client: object, config: RequestConfig) -> object:
        return client

    from chattice.client.executor import OperationExecutor

    app_client: object = await OperationExecutor[object](bot).execute(
        Operation.MESSAGES_GET, identity=AuthMode.APP, call=echo
    )
    user_client: object = await OperationExecutor[object](bot).execute(
        Operation.MESSAGES_GET, identity=AuthMode.USER, call=echo
    )
    assert app_client is not user_client
