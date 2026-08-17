"""FSMContext bound to (storage, key)."""

from __future__ import annotations

import pytest

from chattice.fsm.context import FSMContext, FSMError
from chattice.fsm.storage import MemoryStorage, StorageKey


def _key() -> StorageKey:
    return StorageKey(user="users/1", space="spaces/A", thread=None)


async def test_state_round_trip() -> None:
    context = FSMContext(MemoryStorage(), _key())
    assert await context.get_state() is None
    await context.set_state("Incident:title")
    assert await context.get_state() == "Incident:title"
    await context.set_state(None)
    assert await context.get_state() is None


async def test_data_merge() -> None:
    context = FSMContext(MemoryStorage(), _key())
    await context.set_data({"a": 1})
    await context.update_data(b=2)
    assert await context.get_data() == {"a": 1, "b": 2}


async def test_finish() -> None:
    context = FSMContext(MemoryStorage(), _key())
    await context.set_state("Incident:title")
    await context.set_data({"a": 1})
    await context.finish()
    assert await context.get_state() is None
    assert await context.get_data() == {}


async def test_no_key_get_state_is_none() -> None:
    context = FSMContext(MemoryStorage(), None)
    assert await context.get_state() is None


async def test_no_key_mutations_raise() -> None:
    context = FSMContext(MemoryStorage(), None)
    with pytest.raises(FSMError):
        await context.set_state("Incident:title")
    with pytest.raises(FSMError):
        await context.update_data(a=1)
    with pytest.raises(FSMError):
        await context.finish()
