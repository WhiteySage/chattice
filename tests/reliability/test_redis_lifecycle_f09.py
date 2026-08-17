"""F09 regression: renew TTL, client ownership, JSONValue boundary."""

from __future__ import annotations

from typing import Any

import pytest
from fakeredis import aioredis as fakeredis_aioredis

from chattice.fsm import RedisStorage, StorageKey
from chattice.fsm.record import FSMRecord, RedisFSMRecordStorage
from chattice.idempotency import RedisIdempotencyStorage

# ------------------------------------------------------------ renew keeps TTL


async def test_renew_preserves_the_lease_ttl() -> None:
    """The audit's probe: after renew the key must still EXPIRE (a plain
    SET dropped the TTL and the key would live forever)."""
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    storage = RedisIdempotencyStorage(redis=redis)
    await storage.claim("k", owner="a", lease_seconds=60)
    assert await storage.renew("k", owner="a", lease_seconds=60)
    ttl_ms = await redis.pttl("chattice:idem:k")
    assert 0 < ttl_ms <= 60_000  # a renewed lease, not -1 (no expiry)


async def test_renew_wrong_owner_refused() -> None:
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    storage = RedisIdempotencyStorage(redis=redis)
    await storage.claim("k", owner="a", lease_seconds=60)
    assert not await storage.renew("k", owner="b", lease_seconds=60)


async def test_renew_missing_key_refused() -> None:
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    storage = RedisIdempotencyStorage(redis=redis)
    assert not await storage.renew("missing", owner="a", lease_seconds=60)


# ------------------------------------------------------- ownership / close


class _CloseCountingRedis:
    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


@pytest.mark.parametrize(
    "factory",
    [
        lambda redis: RedisIdempotencyStorage(redis=redis),
        lambda redis: RedisStorage(redis=redis),
        lambda redis: RedisFSMRecordStorage(redis=redis),
    ],
)
async def test_injected_client_never_closed(factory: Any) -> None:
    fake = _CloseCountingRedis()
    storage = factory(fake)
    await storage.aclose()
    await storage.aclose()
    assert fake.closed == 0  # injected clients are caller-owned


async def test_owned_client_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeOwned:
        closed = 0

        @classmethod
        async def aclose(cls) -> None:
            cls.closed += 1

    monkeypatch.setattr("redis.asyncio.from_url", lambda url, **kw: _FakeOwned())
    storage = RedisIdempotencyStorage(url="redis://x")
    await storage.aclose()
    await storage.aclose()  # idempotent
    assert _FakeOwned.closed == 1


# ------------------------------------------------------------ JSONValue


def test_record_rejects_non_json_data() -> None:
    with pytest.raises(TypeError, match="JSON-serializable"):
        FSMRecord(state="s", data={"callback": lambda: None})


def test_record_accepts_json_data_and_enum_values() -> None:
    from enum import Enum

    class Color(Enum):
        RED = "red"

    record = FSMRecord(state="s", data={"n": 1, "nested": {"ok": True}, "c": Color.RED})
    assert dict(record.data) == {"n": 1, "nested": {"ok": True}, "c": "red"}


async def test_redis_record_store_roundtrip_preserves_ttl() -> None:
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    storage = RedisFSMRecordStorage(redis=redis)
    key = StorageKey(user="u", space="s", thread=None)
    await storage.compare_and_set(key, 0, FSMRecord(state="start", data={"a": 1}))
    record = await storage.get_record(key)
    assert record is not None and record.state == "start"


async def test_legacy_redis_storage_update_still_works() -> None:
    """The legacy surface stays functional while DEPRECATE_LATER is in
    effect; docs steer production to the record storage."""
    redis = fakeredis_aioredis.FakeRedis(decode_responses=True)
    storage = RedisStorage(redis=redis)
    key = StorageKey(user="u", space="s", thread=None)
    merged = await storage.update_data(key, {"a": 1})
    assert merged == {"a": 1}
    merged = await storage.update_data(key, {"b": 2})
    assert merged == {"a": 1, "b": 2}
