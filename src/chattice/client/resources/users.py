# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""User read-state and notification clients: USER-only (ADR-012).

Five curated methods mirroring the official ``users.spaces.*`` surface:
read state get/update, thread read state get, notification setting
get/update. Availability is deliberately not a resource here — it is a
rare RPC over one custom status and stays on the raw tier.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, cast

from google.apps.chat_v1.types.space_notification_setting import (
    SpaceNotificationSetting,
)
from google.apps.chat_v1.types.space_read_state import SpaceReadState
from google.apps.chat_v1.types.thread_read_state import (
    ThreadReadState as ThreadReadStateProto,
)
from google.protobuf import field_mask_pb2  # type: ignore[import-untyped]

from chattice.auth import AuthMode
from chattice.capabilities.operations import Operation
from chattice.client.config import RequestConfig
from chattice.client.executor import OperationExecutor
from chattice.client.resources.base import ResourceClient, _effective_config

if TYPE_CHECKING:
    from chattice.client.bot import Bot

__all__ = ["Users"]


class ReadState(ResourceClient):
    """Space read state for the current user."""

    async def get(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> SpaceReadState:
        """Get the read state of ``spaces/{id}`` for the current user."""
        effective = _effective_config(config, timeout)
        return cast(
            SpaceReadState,
            await self._executor.execute(
                Operation.SPACE_READ_STATE_GET,
                identity=self._identity,
                call=lambda client, cfg: client.get_space_read_state(
                    name=name, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def update(
        self,
        name: str,
        *,
        last_read_time: datetime | None,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> SpaceReadState:
        """Update the last-read timestamp of ``spaces/{id}``.

        ``last_read_time=None`` clears the read state (marks unread).
        """
        effective = _effective_config(config, timeout)
        # proto-plus converts datetime <-> Timestamp transparently.
        state = SpaceReadState(name=name, last_read_time=last_read_time)
        mask = field_mask_pb2.FieldMask(paths=["last_read_time"])
        return cast(
            SpaceReadState,
            await self._executor.execute(
                Operation.SPACE_READ_STATE_UPDATE,
                identity=self._identity,
                call=lambda client, cfg: client.update_space_read_state(
                    space_read_state=state,
                    update_mask=mask,
                    **OperationExecutor.gapic_kwargs(cfg),
                ),
                config=effective,
            ),
        )


class ThreadReadState(ResourceClient):
    """Thread read state for the current user."""

    async def get(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> ThreadReadStateProto:
        """Get the read state of a thread for the current user."""
        effective = _effective_config(config, timeout)
        return cast(
            ThreadReadStateProto,
            await self._executor.execute(
                Operation.THREAD_READ_STATE_GET,
                identity=self._identity,
                call=lambda client, cfg: client.get_thread_read_state(
                    name=name, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )


class NotificationSetting(ResourceClient):
    """Space notification settings for the current user."""

    async def get(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> SpaceNotificationSetting:
        """Get notification settings of ``spaces/{id}`` for the current user."""
        effective = _effective_config(config, timeout)
        return cast(
            SpaceNotificationSetting,
            await self._executor.execute(
                Operation.NOTIFICATION_SETTING_GET,
                identity=self._identity,
                call=lambda client, cfg: client.get_space_notification_setting(
                    name=name, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def update(
        self,
        name: str,
        *,
        setting: SpaceNotificationSetting,
        update_mask: Sequence[str],
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> SpaceNotificationSetting:
        """Patch notification settings of ``spaces/{id}`` for the current user."""
        effective = _effective_config(config, timeout)
        setting.name = name
        mask = field_mask_pb2.FieldMask(paths=list(update_mask))
        return cast(
            SpaceNotificationSetting,
            await self._executor.execute(
                Operation.NOTIFICATION_SETTING_UPDATE,
                identity=self._identity,
                call=lambda client, cfg: client.update_space_notification_setting(
                    space_notification_setting=setting,
                    update_mask=mask,
                    **OperationExecutor.gapic_kwargs(cfg),
                ),
                config=effective,
            ),
        )


class Users:
    """Namespace of USER-only per-user state clients (ADR-012)."""

    def __init__(self, bot: Bot, identity: AuthMode) -> None:
        self._bot = bot
        self._identity = identity

    @property
    def read_state(self) -> ReadState:
        """Space read state operations."""
        return ReadState(self._bot, self._identity)

    @property
    def thread_read_state(self) -> ThreadReadState:
        """Thread read state operations."""
        return ThreadReadState(self._bot, self._identity)

    @property
    def notification_setting(self) -> NotificationSetting:
        """Space notification setting operations."""
        return NotificationSetting(self._bot, self._identity)
