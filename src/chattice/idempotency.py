"""Owner-safe push idempotency: claimed(owner, lease) -> completed.

Post-Phase-15 review finding B1: a TTL presence bit can acknowledge work
that never completed. The contract is now a small state machine:

    claim(key, owner, lease)  -> FIRST | COMPLETED | ACTIVE
    complete(key, owner)      -> mark done (keeps absorbing duplicates)
    release(key, owner)       -> drop the claim (only the OWNER may)
    renew(key, owner, lease)  -> extend a long handler's lease

A second delivery that observes another owner's ACTIVE claim answers 429
(«still processing») so Pub/Sub redelivers later — it is never
acknowledged as a completed duplicate. Keys must be namespaced by the
caller (subscription/topic + messageId): Google message IDs are unique
per topic only.

Memory is process-local; Redis stores one JSON document per key with
claim via SET NX and owner-checked release via WATCH/MULTI.
"""

from __future__ import annotations

import asyncio
import enum
import inspect
import json
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

__all__ = [
    "ClaimResult",
    "IdempotencyStorage",
    "MemoryIdempotencyStorage",
    "RedisIdempotencyStorage",
    "new_owner",
]

Clock: TypeAlias = Callable[[], float]

if TYPE_CHECKING:
    from redis import asyncio as aioredis


class ClaimResult(enum.Enum):
    """Outcome of claim(): who owns the delivery now."""

    FIRST = "first"  # this owner claimed it: dispatch
    COMPLETED = "completed"  # a previous owner finished: absorb as duplicate
    ACTIVE = "active"  # another owner is still processing: retry later


def new_owner() -> str:
    """A fresh owner token for one delivery attempt."""
    return uuid.uuid4().hex


class IdempotencyStorage(Protocol):
    """Owner-safe claim/complete/release contract for push dedupe."""

    async def claim(
        self, key: str, *, owner: str, lease_seconds: float
    ) -> ClaimResult: ...

    async def complete(self, key: str, *, owner: str) -> None: ...

    async def release(self, key: str, *, owner: str) -> None: ...

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool: ...


class MemoryIdempotencyStorage:
    """In-process state machine (per-key asyncio locks)."""

    def __init__(self, *, clock: Clock = time.time) -> None:
        self._claims: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._clock = clock

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _prune_expired(self, key: str) -> None:
        claim = self._claims.get(key)
        if claim is not None and not claim["completed"]:
            if claim["lease_until"] <= self._clock():
                del self._claims[key]

    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> ClaimResult:
        async with self._lock_for(key):
            self._prune_expired(key)
            claim = self._claims.get(key)
            if claim is None:
                self._claims[key] = {
                    "owner": owner,
                    "lease_until": self._clock() + lease_seconds,
                    "completed": False,
                }
                return ClaimResult.FIRST
            if claim["completed"]:
                return ClaimResult.COMPLETED
            return ClaimResult.ACTIVE

    async def complete(self, key: str, *, owner: str) -> None:
        async with self._lock_for(key):
            claim = self._claims.get(key)
            if claim is not None and claim["owner"] == owner:
                claim["completed"] = True

    async def release(self, key: str, *, owner: str) -> None:
        async with self._lock_for(key):
            claim = self._claims.get(key)
            if claim is not None and claim["owner"] == owner:
                del self._claims[key]

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        async with self._lock_for(key):
            claim = self._claims.get(key)
            if claim is None or claim["owner"] != owner or claim["completed"]:
                return False
            claim["lease_until"] = self._clock() + lease_seconds
            return True


_DEFAULT_URL = "redis://localhost:6379/0"


class RedisIdempotencyStorage:
    """Redis state machine: SET NX claim, owner-checked WATCH/MULTI ops."""

    def __init__(
        self,
        redis: aioredis.Redis | None = None,
        *,
        url: str = _DEFAULT_URL,
        prefix: str = "chattice:idem",
        clock: Clock = time.time,
        completed_retention_seconds: float = 86400.0,
    ) -> None:
        from redis import asyncio as aioredis

        if redis is not None:
            self._redis = redis
        else:
            self._redis = aioredis.from_url(  # type: ignore[no-untyped-call]
                url, decode_responses=True
            )
        self._prefix = prefix
        self._clock = clock
        self._completed_ttl_ms = max(1, int(completed_retention_seconds * 1000))
        self._owns_redis = redis is None
        self._redis_closed = False

    async def aclose(self) -> None:
        """Close the internally created client (idempotent).

        An injected client is never closed by the storage.
        """
        if not self._owns_redis or self._redis_closed:
            return
        self._redis_closed = True
        closer = getattr(self._redis, "aclose", None) or getattr(
            self._redis, "close", None
        )
        if closer is None:
            return
        result = closer()
        if inspect.isawaitable(result):
            await result

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    @staticmethod
    def _encode(owner: str, lease_until: float, completed: bool) -> str:
        return json.dumps(
            {"o": owner, "l": lease_until, "c": completed}, separators=(",", ":")
        )

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        payload = json.loads(raw)
        return {
            "owner": payload["o"],
            "lease_until": payload["l"],
            "completed": payload["c"],
        }

    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> ClaimResult:
        from redis.exceptions import WatchError

        redis_key = self._key(key)
        value = self._encode(owner, self._clock() + lease_seconds, False)
        px = max(1, int(lease_seconds * 1000))
        first = await self._redis.set(redis_key, value, nx=True, px=px)
        if first:
            return ClaimResult.FIRST
        while True:
            # Expired-takeover MUST be a single conditional decision:
            # WATCH the key, verify the EXACT claim we read is still the
            # expired one, then replace inside MULTI/EXEC. An
            # unconditional SET would let two reclaimers both win.
            async with self._redis.pipeline() as pipe:
                try:
                    await pipe.watch(redis_key)
                    raw = await pipe.get(redis_key)
                    if raw is None:
                        pipe.multi()  # type: ignore[no-untyped-call]
                        pipe.set(redis_key, value, nx=True, px=px)
                        executed = await pipe.execute()
                        return (
                            ClaimResult.FIRST
                            if executed and executed[0]
                            else ClaimResult.ACTIVE
                        )
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    claim = self._decode(raw)
                    if claim["completed"]:
                        return ClaimResult.COMPLETED
                    if claim["lease_until"] > self._clock():
                        return ClaimResult.ACTIVE
                    pipe.multi()  # type: ignore[no-untyped-call]
                    pipe.set(redis_key, value, px=px)
                    await pipe.execute()
                    return ClaimResult.FIRST
                except WatchError:
                    continue  # changed under us: re-read and re-decide

    async def complete(self, key: str, *, owner: str) -> None:
        await self._owner_op(key, owner, completed=True, px=self._completed_ttl_ms)

    async def release(self, key: str, *, owner: str) -> None:
        await self._owner_op(key, owner, delete=True)

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        from redis.exceptions import WatchError

        redis_key = self._key(key)
        while True:
            async with self._redis.pipeline() as pipe:
                try:
                    await pipe.watch(redis_key)
                    raw = await pipe.get(redis_key)
                    if raw is None:
                        return False
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    claim = self._decode(raw)
                    if claim["owner"] != owner or claim["completed"]:
                        return False
                    pipe.multi()  # type: ignore[no-untyped-call]
                    # The renewed lease MUST carry its TTL — a plain
                    # SET discards the previous expiry and the key would
                    # never expire again (audit probe: TTL -1 after renew).
                    pipe.set(
                        redis_key,
                        self._encode(owner, self._clock() + lease_seconds, False),
                        px=max(1, int(lease_seconds * 1000)),
                    )
                    await pipe.execute()
                    return True
                except WatchError:
                    continue

    async def _owner_op(
        self,
        key: str,
        owner: str,
        *,
        completed: bool = False,
        delete: bool = False,
        px: int | None = None,
    ) -> None:
        from redis.exceptions import WatchError

        redis_key = self._key(key)
        while True:
            async with self._redis.pipeline() as pipe:
                try:
                    await pipe.watch(redis_key)
                    raw = await pipe.get(redis_key)
                    if raw is None:
                        return
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    claim = self._decode(raw)
                    if claim["owner"] != owner:
                        return  # never touch another owner's claim
                    pipe.multi()  # type: ignore[no-untyped-call]
                    if delete:
                        pipe.delete(redis_key)
                    elif px is not None:
                        pipe.set(
                            redis_key,
                            self._encode(owner, claim["lease_until"], completed),
                            px=px,
                        )
                    else:
                        pipe.set(
                            redis_key,
                            self._encode(owner, claim["lease_until"], completed),
                        )
                    await pipe.execute()
                    return
                except WatchError:
                    continue
