"""Finite-state machine primitives."""

from typing import TYPE_CHECKING

from .context import FSMContext, FSMError
from .filter import StateFilter
from .record import (
    BaseStorageFromRecord,
    FSMRecord,
    FSMRecordConflict,
    FSMRecordStorage,
    MemoryFSMRecordStorage,
)
from .states import State, StatesGroup
from .storage import BaseStorage, FSMStrategy, MemoryStorage, StorageKey

if TYPE_CHECKING:
    from .record import RedisFSMRecordStorage
    from .redis import RedisStorage

__all__ = [
    "BaseStorage",
    "BaseStorageFromRecord",
    "FSMContext",
    "FSMError",
    "FSMRecord",
    "FSMRecordConflict",
    "FSMRecordStorage",
    "FSMStrategy",
    "MemoryFSMRecordStorage",
    "MemoryStorage",
    "RedisFSMRecordStorage",
    "RedisStorage",
    "State",
    "StateFilter",
    "StatesGroup",
    "StorageKey",
]


def __getattr__(name: str) -> object:
    if name == "RedisStorage":
        from .redis import RedisStorage

        return RedisStorage
    if name == "RedisFSMRecordStorage":
        from .record import RedisFSMRecordStorage

        return RedisFSMRecordStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
