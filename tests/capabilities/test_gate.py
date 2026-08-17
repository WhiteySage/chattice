"""Matrix-driven gate: unsupported combinations fail BEFORE network calls."""

from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported, OutboundCapability
from chattice.client import Bot
from tests.client._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        (AuthMode.NONE, "send_message"),
        (AuthMode.NONE, "update_message"),
    ],
)
async def test_unsupported_combinations_fail_before_network(
    mode: AuthMode, operation: str
) -> None:
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials=_creds(), transport=transport, auth_mode=mode)
    with pytest.raises(CapabilityNotSupported):
        if operation == "send_message":
            await bot.send_message("spaces/AAA", text="x")
        else:
            await bot.update_message("spaces/AAA/messages/1", text="y")
    assert transport.requests == []  # ZERO network calls on failure


async def test_app_mode_lacks_user_impersonation() -> None:
    bot = Bot(credentials=_creds(), auth_mode=AuthMode.APP)
    capabilities = bot.capabilities
    assert capabilities is not None
    with pytest.raises(CapabilityNotSupported):
        capabilities.require(OutboundCapability.USER_IMPERSONATION)


@pytest.mark.parametrize("mode", [AuthMode.APP, AuthMode.USER])
async def test_supported_modes_reach_the_transport(mode: AuthMode) -> None:
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials=_creds(), transport=transport, auth_mode=mode)
    result = await bot.send_message("spaces/AAA", text="x")
    assert result.text == "x"
    assert len(transport.requests) == 1
