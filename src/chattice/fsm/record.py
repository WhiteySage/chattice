"""Next-generation FSM record storage: atomic versioned records.

Handler transitions must be atomic without
exposing distributed lock objects. A record carries the whole FSM state
under one key and transitions use compare-and-set on a revision number:

    FSMRecord(state, data, revision, updated_at, expires_at, schema_version)
    get_record(key) -> record | None
    compare_and_set(key, expected_revision, replacement) -> record

TTL is a whole-record absolute ``expires_at`` with LAZY expiry on access
(no scheduler); a testable clock is injected. ``schema_version`` is a
storage-schema marker; ``flow_version`` remains application data
(deliberately NOT framework metadata).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, cast

from .storage import BaseStorage, StorageKey

if TYPE_CHECKING:
    from redis import asyncio as aioredis

__all__ = [
    "BaseStorageFromRecord",
    "FSMRecord",
    "FSMRecordConflict",
    "FSMRecordStorage",
    "MemoryFSMRecordStorage",
    "RedisFSMRecordStorage",
]

Clock: TypeAlias = Callable[[], float]

_NOT_PROVIDED = object()


class FSMRecordConflict(RuntimeError):
    """A compare-and-set failed: the stored revision differs from expected."""


def _require_json_value(value: object, *, where: str) -> object:
    """Recursive JSONValue contract : memory and Redis record stores
    accept the same domain, failed at the API boundary — not at the
    Redis encoder."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return _require_json_value(value.value, where=where)
    if isinstance(value, Mapping):
        return {
            str(key): _require_json_value(item, where=where)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_require_json_value(item, where=where) for item in value]
    raise TypeError(
        f"{where} must be JSON-serializable (str/int/float/bool/None/"
        f"list/dict); got {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True)
class FSMRecord:
    """One FSM state+data snapshot under a StorageKey.

    ``data`` is validated against the recursive JSONValue contract and
    defensively copied (MappingProxyType) so callers cannot mutate
    stored state without a compare-and-set.
    """

    state: str | None = None
    data: Mapping[str, object] = field(default_factory=dict)
    revision: int = 0
    updated_at: float | None = None
    expires_at: float | None = None
    schema_version: int = 0

    def __post_init__(self) -> None:
        data = cast(
            dict[str, object],
            _require_json_value(dict(self.data), where="FSMRecord.data"),
        )
        object.__setattr__(self, "data", MappingProxyType(data))


class FSMRecordStorage(Protocol):
    """Atomic record contract (optional next-generation storage)."""

    async def get_record(self, key: StorageKey) -> FSMRecord | None:
        """Read the record; an expired record reads as None (lazy TTL)."""
        ...

    async def compare_and_set(
        self,
        key: StorageKey,
        expected_revision: int,
        replacement: FSMRecord,
    ) -> FSMRecord:
        """Atomically store ``replacement`` iff the current record has
        ``expected_revision`` (0 = no record). Returns the stored record
        with its revision bumped; raises FSMRecordConflict otherwise."""
        ...


def _expired(record: FSMRecord, now: float) -> bool:
    return record.expires_at is not None and record.expires_at <= now


class MemoryFSMRecordStorage:
    """In-process record storage: CAS under a per-key asyncio lock."""

    def __init__(self, *, clock: Clock = time.time) -> None:
        self._records: dict[StorageKey, FSMRecord] = {}
        self._locks: dict[StorageKey, asyncio.Lock] = {}
        self._clock = clock

    def _lock_for(self, key: StorageKey) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def get_record(self, key: StorageKey) -> FSMRecord | None:
        async with self._lock_for(key):
            record = self._records.get(key)
            if record is None:
                return None
            if _expired(record, self._clock()):
                del self._records[key]
                return None
            return record

    async def compare_and_set(
        self,
        key: StorageKey,
        expected_revision: int,
        replacement: FSMRecord,
    ) -> FSMRecord:
        async with self._lock_for(key):
            current = self._records.get(key)
            if current is not None and _expired(current, self._clock()):
                del self._records[key]
                current = None
            current_revision = 0 if current is None else current.revision
            if current_revision != expected_revision:
                raise FSMRecordConflict(
                    f"expected revision {expected_revision}, found {current_revision}"
                )
            stored = replace(
                replacement,
                revision=current_revision + 1,
                updated_at=self._clock(),
            )
            self._records[key] = stored
            return stored


_DEFAULT_URL = "redis://localhost:6379/0"


class RedisFSMRecordStorage:
    """Redis record storage: CAS via WATCH/MULTI, whole-record TTL (PX).

    One JSON document per StorageKey; compare-and-set is optimistic with
    retry on watch conflicts (no distributed lock held across I/O).
    """

    def __init__(
        self,
        redis: aioredis.Redis | None = None,
        *,
        url: str = _DEFAULT_URL,
        prefix: str = "chattice:fsmrecord",
        clock: Clock = time.time,
    ) -> None:
        try:
            from redis import asyncio as aioredis
        except ImportError as error:
            raise ImportError(
                "Redis-backed storage requires the `chattice[redis]` extra "
                "(pip install 'chattice[redis]')."
            ) from error

        if redis is not None:
            self._redis = redis
        else:
            self._redis = aioredis.from_url(  # type: ignore[no-untyped-call]
                url, decode_responses=True
            )
        self._prefix = prefix
        self._clock = clock
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

    def _redis_key(self, key: StorageKey) -> str:
        parts = (key.user or "*", key.space or "*", key.thread or "*")
        return f"{self._prefix}:{':'.join(parts)}"

    @staticmethod
    def _encode(record: FSMRecord) -> str:
        return json.dumps(
            {
                "state": record.state,
                "data": dict(record.data),
                "revision": record.revision,
                "updated_at": record.updated_at,
                "expires_at": record.expires_at,
                "schema_version": record.schema_version,
            },
            separators=(",", ":"),
        )

    @staticmethod
    def _decode(raw: str) -> FSMRecord:
        payload = json.loads(raw)
        return FSMRecord(
            state=payload.get("state"),
            data=payload.get("data") or {},
            revision=int(payload.get("revision") or 0),
            updated_at=payload.get("updated_at"),
            expires_at=payload.get("expires_at"),
            schema_version=int(payload.get("schema_version") or 0),
        )

    async def get_record(self, key: StorageKey) -> FSMRecord | None:
        from redis.exceptions import WatchError

        redis_key = self._redis_key(key)
        raw = await self._redis.get(redis_key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        record = self._decode(raw)
        if not _expired(record, self._clock()):
            return record
        # Lazy expiry: delete ONLY the exact value we read — a concurrent
        # writer may have replaced the expired record meanwhile, and a
        # blind delete would destroy the NEW record.
        while True:
            async with self._redis.pipeline() as pipe:
                try:
                    await pipe.watch(redis_key)
                    current_raw = await pipe.get(redis_key)
                    if isinstance(current_raw, bytes):
                        current_raw = current_raw.decode("utf-8")
                    if current_raw != raw:
                        # replaced concurrently: the new value wins
                        if current_raw is None:
                            return None
                        current = self._decode(current_raw)
                        return None if _expired(current, self._clock()) else current
                    pipe.multi()  # type: ignore[no-untyped-call]
                    pipe.delete(redis_key)
                    await pipe.execute()
                    return None
                except WatchError:
                    continue  # changed during watch: re-read and re-decide

    async def compare_and_set(
        self,
        key: StorageKey,
        expected_revision: int,
        replacement: FSMRecord,
    ) -> FSMRecord:
        from redis.exceptions import WatchError

        redis_key = self._redis_key(key)
        while True:
            async with self._redis.pipeline() as pipe:
                try:
                    await pipe.watch(redis_key)
                    raw = await pipe.get(redis_key)
                    current: FSMRecord | None = None
                    if raw is not None:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        current = self._decode(raw)
                    if current is not None and _expired(current, self._clock()):
                        current = None  # lazy TTL: treat as absent
                    current_revision = 0 if current is None else current.revision
                    if current_revision != expected_revision:
                        raise FSMRecordConflict(
                            f"expected revision {expected_revision}, "
                            f"found {current_revision}"
                        )
                    stored = replace(
                        replacement,
                        revision=current_revision + 1,
                        updated_at=self._clock(),
                    )
                    pipe.multi()  # type: ignore[no-untyped-call]
                    if stored.expires_at is not None:
                        ttl_ms = max(1, int((stored.expires_at - self._clock()) * 1000))
                        pipe.set(redis_key, self._encode(stored), px=ttl_ms)
                    else:
                        pipe.set(redis_key, self._encode(stored))
                    await pipe.execute()
                    return stored
                except WatchError:
                    continue  # another writer changed the record; retry


class BaseStorageFromRecord(BaseStorage):
    """Serve the legacy six-method BaseStorage contract over a record store.

    Transitions use compare-and-set; a concurrent modification raises
    FSMRecordConflict instead of silently losing data.
    """

    def __init__(self, record_storage: FSMRecordStorage) -> None:
        self._records = record_storage

    async def get_state(self, key: StorageKey) -> str | None:
        record = await self._records.get_record(key)
        return record.state if record else None

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        await self._mutate(key, state=state)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        record = await self._records.get_record(key)
        return dict(record.data) if record else {}

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._mutate(key, data=dict(data))

    async def update_data(
        self, key: StorageKey, partial: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Read/merge/compare-and-set retry loop: concurrent updates never
        silently overwrite each other (a conflict retries on the new
        revision instead of losing fields)."""
        while True:
            current = await self._records.get_record(key)
            revision = 0 if current is None else current.revision
            merged = dict(current.data) if current else {}
            merged.update(partial)
            try:
                replacement = FSMRecord(
                    state=current.state if current else None,
                    data=merged,
                    expires_at=current.expires_at if current else None,
                    schema_version=current.schema_version if current else 0,
                )
                await self._records.compare_and_set(key, revision, replacement)
                return merged
            except FSMRecordConflict:
                continue  # someone else wrote: re-read and retry

    async def finish(self, key: StorageKey) -> None:
        current = await self._records.get_record(key)
        if current is None:
            return
        await self._mutate(key, state=None, data={})

    async def _mutate(
        self,
        key: StorageKey,
        *,
        state: str | object | None = _NOT_PROVIDED,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        current = await self._records.get_record(key)
        revision = 0 if current is None else current.revision
        if state is _NOT_PROVIDED:
            state_value = current.state if current else None
        else:
            state_value = cast("str | None", state)
        replacement = FSMRecord(
            state=state_value,
            data=data if data is not None else (dict(current.data) if current else {}),
            expires_at=current.expires_at if current else None,
            schema_version=current.schema_version if current else 0,
        )
        await self._records.compare_and_set(key, revision, replacement)
