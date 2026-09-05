"""Resource clients execute through OperationExecutor — one GAPIC path."""

from __future__ import annotations

import pytest
from google.apps.chat_v1.types import Space

from chattice.auth import AuthMode
from chattice.capabilities import Operation
from chattice.client import Bot
from chattice.client.errors import ChatNotFoundError
from chattice.testing import FakeChatTransport
from tests.client.test_identity_clients import _creds


async def test_resource_method_goes_through_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    sentinel = Space(name="spaces/VIA-EXECUTOR")
    executed: list[tuple[Operation, AuthMode]] = []

    async def fake_execute(
        self: object,
        operation: Operation,
        *,
        identity: AuthMode,
        call: object,
        config: object,
    ) -> object:
        executed.append((operation, identity))
        return sentinel

    monkeypatch.setattr(
        "chattice.client.executor.OperationExecutor.execute", fake_execute
    )
    result = await bot.app.spaces.find_direct_message("users/1")

    assert result is sentinel
    assert executed == [(Operation.SPACES_FIND_DIRECT_MESSAGE, AuthMode.APP)]


async def test_get_or_setup_uses_executor_twice_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))
    executed: list[Operation] = []
    find_attempted = False

    async def fake_execute(
        self: object,
        operation: Operation,
        *,
        identity: AuthMode,
        call: object,
        config: object,
    ) -> object:
        executed.append(operation)
        if operation is Operation.SPACES_FIND_DIRECT_MESSAGE:
            nonlocal find_attempted
            find_attempted = True
            raise ChatNotFoundError("no dm")
        return Space(name="spaces/SETUP-VIA-EXECUTOR")

    monkeypatch.setattr(
        "chattice.client.executor.OperationExecutor.execute", fake_execute
    )
    result = await bot.user.spaces.get_or_setup_direct_message("hr@example.com")

    assert result.name == "spaces/SETUP-VIA-EXECUTOR"
    assert find_attempted
    assert executed == [
        Operation.SPACES_FIND_DIRECT_MESSAGE,
        Operation.SPACES_SETUP,
    ]
