"""FSM record storage: CAS, TTL, legacy adapter (B3)."""

from __future__ import annotations

import pytest

from chattice.fsm import (
    BaseStorageFromRecord,
    FSMRecord,
    FSMRecordConflict,
    FSMRecordStorage,
    MemoryFSMRecordStorage,
    StorageKey,
)
from chattice.fsm.record import RedisFSMRecordStorage

_KEY = StorageKey(user="users/1", space="spaces/A", thread=None)


@pytest.fixture(params=["memory", "redis"])
def storage(request: pytest.FixtureRequest) -> FSMRecordStorage:
    if request.param == "memory":
        return MemoryFSMRecordStorage()
    import fakeredis.aioredis

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return RedisFSMRecordStorage(redis=fake)


async def test_record_round_trip(storage: FSMRecordStorage) -> None:
    assert await storage.get_record(_KEY) is None
    stored = await storage.compare_and_set(
        _KEY,
        expected_revision=0,
        replacement=FSMRecord(state="title", data={"n": 1}),
    )
    assert stored.revision == 1
    assert stored.state == "title"
    loaded = await storage.get_record(_KEY)
    assert loaded is not None
    assert loaded == stored


async def test_cas_conflict_raises(storage: FSMRecordStorage) -> None:
    first = await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="a")
    )
    with pytest.raises(FSMRecordConflict, match="revision"):
        await storage.compare_and_set(
            _KEY, expected_revision=0, replacement=FSMRecord(state="b")
        )
    # the correct revision succeeds
    second = await storage.compare_and_set(
        _KEY,
        expected_revision=first.revision,
        replacement=FSMRecord(state="b", data={"x": 1}),
    )
    assert second.revision == 2


async def test_schema_version_is_preserved(storage: FSMRecordStorage) -> None:
    await storage.compare_and_set(
        _KEY,
        expected_revision=0,
        replacement=FSMRecord(state="a", schema_version=3),
    )
    loaded = await storage.get_record(_KEY)
    assert loaded is not None and loaded.schema_version == 3


async def test_lazy_ttl_expiry() -> None:
    clock = {"now": 1000.0}
    storage = MemoryFSMRecordStorage(clock=lambda: clock["now"])
    await storage.compare_and_set(
        _KEY,
        expected_revision=0,
        replacement=FSMRecord(state="a", expires_at=1000.0 + 60),
    )
    clock["now"] = 1000.0 + 61
    assert await storage.get_record(_KEY) is None  # expired lazily


async def test_ttl_survives_until_expiry() -> None:
    clock = {"now": 1000.0}
    storage = MemoryFSMRecordStorage(clock=lambda: clock["now"])
    await storage.compare_and_set(
        _KEY,
        expected_revision=0,
        replacement=FSMRecord(state="a", expires_at=1000.0 + 60),
    )
    clock["now"] = 1000.0 + 30
    loaded = await storage.get_record(_KEY)
    assert loaded is not None and loaded.state == "a"


async def test_updated_at_is_set() -> None:
    storage = MemoryFSMRecordStorage(clock=lambda: 42.0)
    stored = await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="a")
    )
    assert stored.updated_at == 42.0


# --- legacy adapter over a record store ---


@pytest.fixture
def adapter(storage: FSMRecordStorage) -> BaseStorageFromRecord:
    return BaseStorageFromRecord(storage)


async def test_adapter_set_and_get_state(adapter: BaseStorageFromRecord) -> None:
    await adapter.set_state(_KEY, "title")
    assert await adapter.get_state(_KEY) == "title"


async def test_adapter_data_operations(adapter: BaseStorageFromRecord) -> None:
    await adapter.set_data(_KEY, {"a": 1})
    merged = await adapter.update_data(_KEY, {"b": 2})
    assert merged == {"a": 1, "b": 2}
    assert await adapter.get_data(_KEY) == {"a": 1, "b": 2}


async def test_adapter_finish_clears_record(adapter: BaseStorageFromRecord) -> None:
    await adapter.set_state(_KEY, "title")
    await adapter.set_data(_KEY, {"a": 1})
    await adapter.finish(_KEY)
    assert await adapter.get_state(_KEY) is None
    assert await adapter.get_data(_KEY) == {}


async def test_adapter_mutations_bump_revisions_monotonically(
    adapter: BaseStorageFromRecord,
) -> None:
    """Every adapter mutation goes through CAS: revisions grow one by one,
    and a conflicting expectation raises (tested at the CAS level)."""
    record_storage = adapter._records
    await adapter.set_state(_KEY, "title")
    first = await record_storage.get_record(_KEY)
    assert first is not None and first.revision == 1
    await adapter.update_data(_KEY, {"a": 1})
    second = await record_storage.get_record(_KEY)
    assert second is not None and second.revision == 2
    assert second.data == {"a": 1}
    assert second.state == "title"


async def test_record_data_is_immutable() -> None:
    storage = MemoryFSMRecordStorage()
    stored = await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="a", data={"n": 1})
    )
    with pytest.raises(TypeError):
        stored.data["n"] = 2  # type: ignore[index]
    loaded = await storage.get_record(_KEY)
    assert loaded is not None and loaded.data["n"] == 1


async def test_adapter_update_data_preserves_metadata() -> None:
    from chattice.fsm.record import MemoryFSMRecordStorage

    storage = MemoryFSMRecordStorage()
    adapter = BaseStorageFromRecord(storage)
    await adapter.set_state(_KEY, "title")
    record = await storage.get_record(_KEY)
    assert record is not None
    # attach metadata via CAS
    await storage.compare_and_set(
        _KEY,
        expected_revision=record.revision,
        replacement=FSMRecord(
            state=record.state,
            data=dict(record.data),
            expires_at=4102444800.0,  # 2100-01-01: far-future absolute TTL
            schema_version=7,
        ),
    )
    await adapter.update_data(_KEY, {"b": 2})
    updated = await storage.get_record(_KEY)
    assert updated is not None
    assert updated.expires_at == 4102444800.0
    assert updated.schema_version == 7
    assert dict(updated.data) == {"b": 2}


async def test_redis_lazy_expiry_never_deletes_replacement() -> None:
    """B2 regression: a stale reader's lazy delete must not destroy a
    record that a concurrent writer stored in the meantime."""
    import fakeredis.aioredis

    from chattice.fsm.record import RedisFSMRecordStorage

    clock = {"now": 0.0}
    storage = RedisFSMRecordStorage(
        redis=fakeredis.aioredis.FakeRedis(decode_responses=True),
        clock=lambda: clock["now"],
    )
    await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="old", expires_at=10.0)
    )
    clock["now"] = 11.0  # now expired
    # writer replaces the expired record FIRST
    stored = await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="new")
    )
    # stale reader (arrived before the write) reads AFTER the write and
    # must see the NEW record, not delete it
    loaded = await storage.get_record(_KEY)
    assert loaded is not None
    assert loaded.state == "new"
    assert loaded.revision == stored.revision


async def test_redis_expiry_forced_stale_read_interleaving() -> None:
    """S3 regression: force a stale reader to read the expired value, then
    a writer replaces it, THEN the reader's cleanup runs — the new record
    must survive."""
    import asyncio

    import fakeredis.aioredis

    from chattice.fsm.record import RedisFSMRecordStorage

    clock = {"now": 0.0}
    storage = RedisFSMRecordStorage(
        redis=fakeredis.aioredis.FakeRedis(decode_responses=True),
        clock=lambda: clock["now"],
    )
    await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="old", expires_at=10.0)
    )
    clock["now"] = 11.0  # expired

    real_get = storage._redis.get
    stale_read: list[str | None] = []
    gate = asyncio.Event()

    async def slowed_get(key: str) -> object:
        result = await real_get(key)
        if result is not None and not gate.is_set():
            gate.set()
            stale_read.append(result if isinstance(result, str) else result.decode())
            await asyncio.sleep(0.01)  # writer wins in this window
        return result

    storage._redis.get = slowed_get  # type: ignore[method-assign,assignment]
    reader = asyncio.create_task(storage.get_record(_KEY))
    await gate.wait()
    # writer replaces the expired record while the reader holds the stale value
    await storage.compare_and_set(
        _KEY, expected_revision=0, replacement=FSMRecord(state="new")
    )
    result = await reader
    assert result is None or result.state == "new"
    final = await storage.get_record(_KEY)
    assert final is not None and final.state == "new"
