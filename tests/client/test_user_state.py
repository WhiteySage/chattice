"""User read-state and notification clients: USER-only, executor path."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported, Operation
from chattice.client import Bot
from chattice.testing import FakeChatTransport
from tests.client.test_identity_clients import _creds


def _bot() -> Bot:
    return Bot(credentials=_creds(), transport=FakeChatTransport(credentials=_creds()))


async def _record_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Operation, AuthMode]]:
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
    return executed


async def test_read_state_get_goes_through_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = await _record_executor(monkeypatch)
    await _bot().user.users.read_state.get("spaces/A")

    assert executed == [(Operation.SPACE_READ_STATE_GET, AuthMode.USER)]


async def test_read_state_update_builds_timestamp_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RecordingClient:
        def __init__(self, **kwargs: object) -> None:
            self.calls: list[tuple[object, object]] = []

        async def update_space_read_state(self, **kw: object) -> None:
            self.calls.append((kw.get("space_read_state"), kw.get("update_mask")))

    monkeypatch.setattr("chattice.client.bot.ChatServiceAsyncClient", _RecordingClient)
    bot = Bot(
        app_credentials_provider=lambda: _creds(),
        user_credentials_provider=lambda: _user_creds(),
        transport=FakeChatTransport(credentials=_creds()),
    )
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    await bot.user.users.read_state.update("spaces/A", last_read_time=moment)

    user_client = cast(Any, bot._user_client)
    state, mask = user_client.calls[0]
    assert state.name == "spaces/A"
    assert state.last_read_time == moment
    assert list(mask.paths) == ["last_read_time"]


async def test_thread_read_state_get_goes_through_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = await _record_executor(monkeypatch)
    await _bot().user.users.thread_read_state.get("spaces/A/threads/T")

    assert executed == [(Operation.THREAD_READ_STATE_GET, AuthMode.USER)]


async def test_notification_get_goes_through_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = await _record_executor(monkeypatch)
    await _bot().user.users.notification_setting.get("spaces/A")

    assert executed == [(Operation.NOTIFICATION_SETTING_GET, AuthMode.USER)]


async def test_notification_update_goes_through_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = await _record_executor(monkeypatch)
    from google.apps.chat_v1.types.space_notification_setting import (
        SpaceNotificationSetting,
    )

    setting = SpaceNotificationSetting(name="spaces/A")
    await _bot().user.users.notification_setting.update(
        "spaces/A", setting=setting, update_mask=["mute_setting"]
    )

    assert executed == [(Operation.NOTIFICATION_SETTING_UPDATE, AuthMode.USER)]


async def test_app_identity_is_rejected_at_preflight() -> None:
    bot = _bot()

    with pytest.raises(CapabilityNotSupported):
        await bot.app.users.read_state.get("spaces/A")


class _UserCredentials(AnonymousCredentials):
    """Authorized-user stand-in: a refresh_token classifies as USER."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_token = "rt"


def _user_creds() -> AnonymousCredentials:
    return _UserCredentials()
