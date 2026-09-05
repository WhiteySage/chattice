"""MemoryStorage contract."""

from __future__ import annotations

import asyncio

from chattice.fsm.storage import MemoryStorage, StorageKey


def _key() -> StorageKey:
    return StorageKey(user="users/1", space="spaces/A", thread=None)


async def test_state_crud() -> None:
    storage = MemoryStorage()
    assert await storage.get_state(_key()) is None
    await storage.set_state(_key(), "Incident:title")
    assert await storage.get_state(_key()) == "Incident:title"
    await storage.set_state(_key(), None)
    assert await storage.get_state(_key()) is None


async def test_data_crud_and_merge() -> None:
    storage = MemoryStorage()
    await storage.set_data(_key(), {"title": "a"})
    merged = await storage.update_data(_key(), {"severity": "high"})
    assert merged == {"title": "a", "severity": "high"}
    assert await storage.get_data(_key()) == {"title": "a", "severity": "high"}


async def test_finish_clears_everything() -> None:
    storage = MemoryStorage()
    await storage.set_state(_key(), "Incident:title")
    await storage.set_data(_key(), {"x": 1})
    await storage.finish(_key())
    assert await storage.get_state(_key()) is None
    assert await storage.get_data(_key()) == {}


async def test_concurrent_sets_on_one_key() -> None:
    storage = MemoryStorage()
    values = [f"state-{i}" for i in range(10)]

    async def writer(value: str) -> None:
        await storage.set_state(_key(), value)

    await asyncio.gather(*(writer(v) for v in values))
    final = await storage.get_state(_key())
    assert final in values  # last-write-wins, all writes completed


async def test_different_keys_independent() -> None:
    storage = MemoryStorage()
    other = StorageKey(user="users/2", space="spaces/A", thread=None)
    await storage.set_state(_key(), "a")
    await storage.set_state(other, "b")
    assert await storage.get_state(_key()) == "a"
    assert await storage.get_state(other) == "b"
