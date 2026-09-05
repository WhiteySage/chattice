"""Reaction resource client: USER-only, executor path."""

from __future__ import annotations

from typing import Any, cast

import pytest
from google.apps.chat_v1.types.reaction import Reaction
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported, Operation
from chattice.client import Bot
from chattice.testing import FakeChatTransport
from tests.client.test_identity_clients import _creds


def _bot() -> Bot:
    return Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))


async def test_create_goes_through_executor_with_user_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _bot()
    sentinel = Reaction(name="spaces/A/messages/M1/reactions/1")
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
    result = await bot.user.reactions.create("spaces/A/messages/M1", emoji="🚀")

    assert result is sentinel
    assert executed == [(Operation.REACTIONS_CREATE, AuthMode.USER)]


async def test_create_builds_unicode_emoji_reaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RecordingClient:
        def __init__(self, **kwargs: object) -> None:
            self.calls: list[tuple[object, object]] = []

        async def create_reaction(
            self, request: object = None, **kw: object
        ) -> Reaction:
            self.calls.append((request, kw))
            return Reaction(name="spaces/A/messages/M1/reactions/1")

    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _RecordingClient)
    bot = Bot(
        app_credentials_provider=lambda: _creds(),
        user_credentials_provider=lambda: _user_creds(),
        transport=FakeChatTransport(credentials=_creds()),
    )

    await bot.user.reactions.create("spaces/A/messages/M1", emoji="🚀")

    user_client = cast(Any, bot._user_client)
    request, _kwargs = user_client.calls[0]
    assert request["parent"] == "spaces/A/messages/M1"
    assert request["reaction"].emoji.unicode == "🚀"


async def test_list_returns_pager_via_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _bot()
    executed: list[Operation] = []

    class _FakePager:
        def __aiter__(self) -> Any:
            return self

        async def __anext__(self) -> object:
            raise StopAsyncIteration

    async def fake_execute(
        self: object,
        operation: Operation,
        *,
        identity: AuthMode,
        call: object,
        config: object,
    ) -> object:
        executed.append(operation)
        return _FakePager()

    monkeypatch.setattr(
        "chattice.client.executor.OperationExecutor.execute", fake_execute
    )
    pager = await bot.user.reactions.list("spaces/A/messages/M1")

    assert await pager.collect() == []
    assert executed == [Operation.REACTIONS_LIST]


async def test_delete_goes_through_executor_with_user_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = _bot()
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
        return None

    monkeypatch.setattr(
        "chattice.client.executor.OperationExecutor.execute", fake_execute
    )
    await bot.user.reactions.delete("spaces/A/messages/M1/reactions/1")

    assert executed == [(Operation.REACTIONS_DELETE, AuthMode.USER)]


async def test_app_identity_is_rejected_at_preflight() -> None:
    bot = _bot()

    with pytest.raises(CapabilityNotSupported):
        await bot.app.reactions.create("spaces/A/messages/M1", emoji="🚀")


class _UserCredentials(AnonymousCredentials):
    """Authorized-user stand-in: a refresh_token classifies as USER."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_token = "rt"


def _user_creds() -> AnonymousCredentials:
    return _UserCredentials()
