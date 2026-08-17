"""Per-event FSM context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .states import State
from .storage import BaseStorage, StorageKey

__all__ = ["FSMContext", "FSMError"]


class FSMError(RuntimeError):
    """FSM operation attempted without a derivable storage key."""


class FSMContext:
    """Bound to (storage, key) for one event; injected by the dispatcher."""

    def __init__(self, storage: BaseStorage, key: StorageKey | None) -> None:
        self._storage = storage
        self._key = key

    def _require_key(self) -> StorageKey:
        if self._key is None:
            raise FSMError(
                "Cannot derive an FSM storage key for this event "
                "(missing user/space refs for the configured strategy)"
            )
        return self._key

    async def get_state(self) -> str | None:
        if self._key is None:
            return None
        return await self._storage.get_state(self._key)

    async def set_state(self, state: str | State | None) -> None:
        if isinstance(state, State):
            state = state.state
        await self._storage.set_state(self._require_key(), state)

    async def get_data(self) -> dict[str, Any]:
        if self._key is None:
            return {}
        return await self._storage.get_data(self._key)

    async def set_data(self, data: Mapping[str, Any]) -> None:
        await self._storage.set_data(self._require_key(), data)

    async def update_data(self, **partial: Any) -> dict[str, Any]:
        return await self._storage.update_data(self._require_key(), partial)

    async def finish(self) -> None:
        await self._storage.finish(self._require_key())
