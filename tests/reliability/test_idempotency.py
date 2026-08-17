"""Idempotency owner-safe state machine (Memory + Redis/fakeredis)."""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis_aioredis

from chattice.idempotency import (
    ClaimResult,
    IdempotencyStorage,
    MemoryIdempotencyStorage,
    RedisIdempotencyStorage,
)


def _memory() -> IdempotencyStorage:
    return MemoryIdempotencyStorage()


def _redis() -> IdempotencyStorage:
    return RedisIdempotencyStorage(
        redis=fakeredis_aioredis.FakeRedis(decode_responses=True)
    )


@pytest.fixture(params=["memory", "redis"])
def storage(request: pytest.FixtureRequest) -> IdempotencyStorage:
    return _memory() if request.param == "memory" else _redis()


async def test_first_claim(storage: IdempotencyStorage) -> None:
    assert await storage.claim("k", owner="a", lease_seconds=60) is ClaimResult.FIRST


async def test_completed_claim_is_absorbed(storage: IdempotencyStorage) -> None:
    await storage.claim("k", owner="a", lease_seconds=60)
    await storage.complete("k", owner="a")
    assert (
        await storage.claim("k", owner="b", lease_seconds=60) is ClaimResult.COMPLETED
    )


async def test_active_claim_is_not_absorbed(storage: IdempotencyStorage) -> None:
    await storage.claim("k", owner="a", lease_seconds=60)
    assert await storage.claim("k", owner="b", lease_seconds=60) is ClaimResult.ACTIVE


async def test_release_requires_owner(storage: IdempotencyStorage) -> None:
    await storage.claim("k", owner="a", lease_seconds=60)
    await storage.release("k", owner="b")  # wrong owner: no-op
    assert await storage.claim("k", owner="c", lease_seconds=60) is ClaimResult.ACTIVE
    await storage.release("k", owner="a")
    assert await storage.claim("k", owner="c", lease_seconds=60) is ClaimResult.FIRST


async def test_release_enables_redispatch(storage: IdempotencyStorage) -> None:
    await storage.claim("k", owner="a", lease_seconds=60)
    await storage.release("k", owner="a")  # failed dispatch
    assert await storage.claim("k", owner="b", lease_seconds=60) is ClaimResult.FIRST


async def test_renew_extends_lease(storage: IdempotencyStorage) -> None:
    await storage.claim("k", owner="a", lease_seconds=60)
    assert await storage.renew("k", owner="a", lease_seconds=120) is True
    assert await storage.renew("k", owner="b", lease_seconds=120) is False


async def test_expired_lease_can_be_taken_over() -> None:
    clock = {"now": 0.0}
    storage = MemoryIdempotencyStorage(clock=lambda: clock["now"])
    await storage.claim("k", owner="a", lease_seconds=60)
    clock["now"] = 61.0
    assert await storage.claim("k", owner="b", lease_seconds=60) is ClaimResult.FIRST


async def test_completed_survives_lease_expiry() -> None:
    clock = {"now": 0.0}
    storage = MemoryIdempotencyStorage(clock=lambda: clock["now"])
    await storage.claim("k", owner="a", lease_seconds=60)
    await storage.complete("k", owner="a")
    clock["now"] = 61.0
    assert (
        await storage.claim("k", owner="b", lease_seconds=60) is ClaimResult.COMPLETED
    )


async def test_redis_expired_takeover_is_single_owner() -> None:
    """B1 regression: two reclaimers racing on an expired lease must NOT
    both receive FIRST (conditional takeover inside WATCH/MULTI)."""
    import asyncio

    clock = {"now": 0.0}
    storage = RedisIdempotencyStorage(
        redis=fakeredis_aioredis.FakeRedis(decode_responses=True),
        clock=lambda: clock["now"],
    )
    await storage.claim("k", owner="a", lease_seconds=60)
    clock["now"] = 61.0  # expired
    results = await asyncio.gather(
        storage.claim("k", owner="b", lease_seconds=60),
        storage.claim("k", owner="c", lease_seconds=60),
    )
    assert results.count(ClaimResult.FIRST) == 1


async def test_redis_expired_takeover_forced_interleaving() -> None:
    """S1 regression: force a yield between the reclaimer's read and its
    MULTI/EXEC — the second reclaimer must NOT also win FIRST."""
    import asyncio

    clock = {"now": 0.0}
    storage = RedisIdempotencyStorage(
        redis=fakeredis_aioredis.FakeRedis(decode_responses=True),
        clock=lambda: clock["now"],
    )
    await storage.claim("k", owner="a", lease_seconds=60)
    clock["now"] = 61.0  # expired

    real_get = storage._redis.get
    gate = asyncio.Event()

    async def slowed_get(key: str) -> object:
        result = await real_get(key)
        if result is not None and not gate.is_set():
            gate.set()
            await asyncio.sleep(0.01)  # force the race window
        return result

    storage._redis.get = slowed_get  # type: ignore[method-assign,assignment]
    results = await asyncio.gather(
        storage.claim("k", owner="b", lease_seconds=60),
        storage.claim("k", owner="c", lease_seconds=60),
    )
    assert results.count(ClaimResult.FIRST) == 1
