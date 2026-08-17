"""Dispatcher pre-injects data["state"] before filters when fsm_storage is set."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event, MessageEvent
from chattice.fsm import FSMContext, MemoryStorage, StateFilter
from chattice.fsm.states import State, StatesGroup


class Incident(StatesGroup):
    title = State()


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


async def test_state_available_to_filters_and_handlers() -> None:
    dispatcher = Dispatcher(fsm_storage=MemoryStorage())
    router = Router()
    seen: list[str] = []

    @router.message(StateFilter(Incident.title))
    async def handler(message: MessageEvent, state: FSMContext) -> str:
        seen.append(str(await state.get_state()))
        return "ok"

    dispatcher.include_router(router)
    result = await dispatcher.feed_update(_event())
    # State is None on the first message -> filter does not match.
    assert result is None
    assert seen == []


async def test_state_transitions_through_filters() -> None:
    storage = MemoryStorage()
    dispatcher = Dispatcher(fsm_storage=storage)
    router = Router()
    results: list[str] = []

    @router.message(StateFilter(Incident.title))
    async def title_handler(message: MessageEvent, state: FSMContext) -> str:
        results.append("matched")
        return "matched"

    @router.message()
    async def fallback(message: MessageEvent, state: FSMContext) -> str:
        await state.set_state(Incident.title)
        results.append("set")
        return "set"

    dispatcher.include_router(router)
    first = await dispatcher.feed_update(_event())  # no state -> fallback sets it
    second = await dispatcher.feed_update(_event())  # now state matches
    assert first == "set"
    assert second == "matched"
    assert results == ["set", "matched"]


async def test_without_fsm_storage_nothing_changes() -> None:
    dispatcher = Dispatcher()  # no fsm_storage
    router = Router()

    @router.message()
    async def handler(message: MessageEvent, state: FSMContext) -> None:
        return None

    dispatcher.include_router(router)
    try:
        await dispatcher.feed_update(_event())
    except Exception as error:  # DependencyResolutionError: missing 'state'
        assert "state" in str(error)
    else:  # pragma: no cover
        raise AssertionError("handler without fsm config must fail on 'state' DI")
