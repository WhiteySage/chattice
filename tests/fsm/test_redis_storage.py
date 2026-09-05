"""RedisStorage contract on fakeredis (parametrized with MemoryStorage)."""

from __future__ import annotations

import asyncio

import pytest
from fakeredis import aioredis as fakeredis_aioredis

from chattice.fsm import MemoryStorage, RedisStorage
from chattice.fsm.storage import BaseStorage, StorageKey


def _key() -> StorageKey:
    return StorageKey(user="users/1", space="spaces/A", thread=None)


def _redis_storage() -> RedisStorage:
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    return RedisStorage(redis=redis)


@pytest.fixture(params=["memory", "redis"])
def storage(request: pytest.FixtureRequest) -> BaseStorage:
    return MemoryStorage() if request.param == "memory" else _redis_storage()


@pytest.mark.parametrize("storage", ["memory", "redis"], indirect=True)
async def test_state_crud(storage: BaseStorage) -> None:
    assert await storage.get_state(_key()) is None
    await storage.set_state(_key(), "Incident:title")
    assert await storage.get_state(_key()) == "Incident:title"
    await storage.set_state(_key(), None)
    assert await storage.get_state(_key()) is None


@pytest.mark.parametrize("storage", ["memory", "redis"], indirect=True)
async def test_data_crud_and_merge(storage: BaseStorage) -> None:
    await storage.set_data(_key(), {"title": "a"})
    merged = await storage.update_data(_key(), {"severity": "high"})
    assert merged == {"title": "a", "severity": "high"}
    assert await storage.get_data(_key()) == {"title": "a", "severity": "high"}


@pytest.mark.parametrize("storage", ["memory", "redis"], indirect=True)
async def test_finish_clears_everything(storage: BaseStorage) -> None:
    await storage.set_state(_key(), "Incident:title")
    await storage.set_data(_key(), {"x": 1})
    await storage.finish(_key())
    assert await storage.get_state(_key()) is None
    assert await storage.get_data(_key()) == {}


@pytest.mark.parametrize("storage", ["memory", "redis"], indirect=True)
async def test_concurrent_sets_on_one_key(storage: BaseStorage) -> None:
    values = [f"state-{i}" for i in range(10)]

    async def writer(value: str) -> None:
        await storage.set_state(_key(), value)

    await asyncio.gather(*(writer(v) for v in values))
    final = await storage.get_state(_key())
    assert final in values


@pytest.mark.parametrize("storage", ["memory", "redis"], indirect=True)
async def test_different_keys_independent(storage: BaseStorage) -> None:
    other = StorageKey(user="users/2", space="spaces/A", thread=None)
    await storage.set_state(_key(), "a")
    await storage.set_state(other, "b")
    assert await storage.get_state(_key()) == "a"
    assert await storage.get_state(other) == "b"


async def test_bytes_returning_client_is_supported() -> None:
    """A client without decode_responses (bytes) must still round-trip state."""
    redis = fakeredis_aioredis.FakeRedis(decode_responses=False)
    storage = RedisStorage(redis=redis)
    await storage.set_state(_key(), "Incident:title")
    assert await storage.get_state(_key()) == "Incident:title"
