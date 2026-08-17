"""StateFilter matching."""

from __future__ import annotations

from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event
from chattice.fsm import FSMContext, MemoryStorage, StateFilter, StorageKey
from chattice.fsm.states import State, StatesGroup


class Incident(StatesGroup):
    title = State()
    severity = State()


def _event() -> Event:
    return parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2026-08-13T12:35:00Z",
            "message": {"text": "x"},
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
        }
    )


async def _data_with_state(state: str | None) -> dict[str, object]:
    storage = MemoryStorage()
    key = StorageKey(user="users/1", space="spaces/A", thread=None)
    if state is not None:
        await storage.set_state(key, state)
    return {"state": FSMContext(storage, key)}


async def test_matching_state() -> None:
    filter_ = StateFilter(Incident.title)
    assert await filter_(_event(), await _data_with_state("Incident:title"))


async def test_non_matching_state() -> None:
    filter_ = StateFilter(Incident.title)
    assert not await filter_(_event(), await _data_with_state("Incident:severity"))


async def test_empty_filter_matches_any_state() -> None:
    filter_ = StateFilter()
    assert await filter_(_event(), await _data_with_state("Incident:severity"))
    assert not await filter_(_event(), await _data_with_state(None))


async def test_absent_context_does_not_match() -> None:
    filter_ = StateFilter(Incident.title)
    assert not await filter_(_event(), {})
