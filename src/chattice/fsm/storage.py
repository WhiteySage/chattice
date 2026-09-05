"""FSM storage primitives."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from chattice.events import Event

__all__ = [
    "BaseStorage",
    "FSMStrategy",
    "MemoryStorage",
    "StorageKey",
]


class FSMStrategy(Enum):
    """How the storage key is derived from an event."""

    USER_IN_SPACE = "user_in_space"
    USER = "user"
    SPACE = "space"


@dataclass(frozen=True, slots=True)
class StorageKey:
    """The composite identity an FSM record is stored under."""

    user: str | None
    space: str | None
    thread: str | None

    @classmethod
    def build(cls, event: Event, strategy: FSMStrategy) -> StorageKey | None:
        """Derive the key from the event refs; None when refs are missing."""
        user = event.actor.name if event.actor is not None else None
        space = event.space.name if event.space is not None else None
        thread = event.thread.name if event.thread is not None else None
        if strategy is FSMStrategy.USER_IN_SPACE:
            if user is None or space is None:
                return None
            return cls(user=user, space=space, thread=thread)
        if strategy is FSMStrategy.USER:
            if user is None:
                return None
            return cls(user=user, space=None, thread=None)
        if strategy is FSMStrategy.SPACE:
            if space is None:
                return None
            return cls(user=None, space=space, thread=None)
        raise ValueError(f"Unknown FSMStrategy {strategy!r}")


class BaseStorage(Protocol):
    """Storage contract implemented by MemoryStorage and RedisStorage."""

    async def get_state(self, key: StorageKey) -> str | None: ...
    async def set_state(self, key: StorageKey, state: str | None) -> None: ...
    async def get_data(self, key: StorageKey) -> dict[str, Any]: ...
    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None: ...
    async def update_data(
        self, key: StorageKey, partial: Mapping[str, Any]
    ) -> dict[str, Any]: ...
    async def finish(self, key: StorageKey) -> None: ...


@dataclass
class _Record:
    state: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class MemoryStorage:
    """In-process storage.

    Concurrency guarantees are process-local: per-key asyncio locks serialize
    writes within one event loop; nothing here survives across processes.
    """

    def __init__(self) -> None:
        self._records: dict[StorageKey, _Record] = {}
        self._locks: dict[StorageKey, asyncio.Lock] = {}

    def _lock_for(self, key: StorageKey) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _record(self, key: StorageKey) -> _Record:
        record = self._records.get(key)
        if record is None:
            record = _Record()
            self._records[key] = record
        return record

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._lock_for(key):
            record = self._records.get(key)
            return record.state if record is not None else None

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        async with self._lock_for(key):
            if state is None and key not in self._records:
                return
            self._record(key).state = state

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._lock_for(key):
            record = self._records.get(key)
            return dict(record.data) if record is not None else {}

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        async with self._lock_for(key):
            self._record(key).data = dict(data)

    async def update_data(
        self, key: StorageKey, partial: Mapping[str, Any]
    ) -> dict[str, Any]:
        async with self._lock_for(key):
            record = self._record(key)
            record.data.update(partial)
            return dict(record.data)

    async def finish(self, key: StorageKey) -> None:
        async with self._lock_for(key):
            self._records.pop(key, None)
