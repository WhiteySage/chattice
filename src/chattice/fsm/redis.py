"""Redis-backed FSM storage (optional extra chattice[redis]).

Concurrency honesty: Redis commands are atomic individually. update_data is
GET -> SET under a process-local lock, so cross-process update_data races
are NOT prevented (per the master plan's "do not pretend" rule). Use
set_data for replace semantics.

DEPRECATE_LATER : ``update_data`` is not multi-process safe. For
production cross-process use, prefer
``BaseStorageFromRecord(RedisFSMRecordStorage(...))`` — its compare-and-set
retry loop never silently loses updates. The legacy key layout here is
preserved until the migration is published.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Mapping
from typing import Any

try:
    from redis import asyncio as aioredis
except ImportError as error:  # pragma: no cover - env-dependent
    raise ImportError(
        "Redis-backed storage requires the `chattice[redis]` extra "
        "(pip install 'chattice[redis]')."
    ) from error

from .storage import StorageKey

__all__ = ["RedisStorage"]

_DEFAULT_URL = "redis://localhost:6379/0"


class RedisStorage:
    """FSM storage over redis.asyncio with a namespaced key layout."""

    def __init__(
        self,
        redis: aioredis.Redis | None = None,
        *,
        url: str = _DEFAULT_URL,
        prefix: str = "chattice:fsm",
    ) -> None:
        if redis is not None:
            self._redis = redis
        else:
            # redis.asyncio.from_url is untyped in redis 6.4; it returns a client.
            # decode_responses=True is required so get() returns str, not bytes.
            self._redis = aioredis.from_url(  # type: ignore[no-untyped-call]
                url, decode_responses=True
            )
        self._prefix = prefix
        self._locks: dict[str, asyncio.Lock] = {}
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

    def _lock_for(self, redis_key: str) -> asyncio.Lock:
        lock = self._locks.get(redis_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[redis_key] = lock
        return lock

    def _base(self, key: StorageKey) -> str:
        parts = (key.user or "*", key.space or "*", key.thread or "*")
        return f"{self._prefix}:{':'.join(parts)}"

    def _state_key(self, key: StorageKey) -> str:
        return f"{self._base(key)}:state"

    def _data_key(self, key: StorageKey) -> str:
        return f"{self._base(key)}:data"

    async def get_state(self, key: StorageKey) -> str | None:
        raw = await self._redis.get(self._state_key(key))
        if isinstance(raw, str):
            return raw
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return None

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        state_key = self._state_key(key)
        if state is None:
            await self._redis.delete(state_key)
        else:
            await self._redis.set(state_key, state)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        raw = await self._redis.get(self._data_key(key))
        if raw is None:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._redis.set(self._data_key(key), json.dumps(dict(data)))

    async def update_data(
        self, key: StorageKey, partial: Mapping[str, Any]
    ) -> dict[str, Any]:
        data_key = self._data_key(key)
        async with self._lock_for(data_key):
            merged = await self.get_data(key)
            merged.update(partial)
            await self._redis.set(data_key, json.dumps(merged))
            return merged

    async def finish(self, key: StorageKey) -> None:
        await self._redis.delete(self._state_key(key), self._data_key(key))
