"""Phase gate: multi-step workflow on MemoryStorage and RedisStorage (fakeredis)."""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis_aioredis

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event, MessageEvent
from chattice.fsm import (
    FSMContext,
    MemoryStorage,
    RedisStorage,
    StateFilter,
    StorageKey,
)
from chattice.fsm.states import State, StatesGroup
from chattice.fsm.storage import BaseStorage


class Incident(StatesGroup):
    title = State()
    severity = State()
    confirmation = State()


def _message(text: str) -> Event:
    return parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2026-08-13T12:35:00Z",
            "message": {"text": text},
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
        }
    )


def _storage(kind: str) -> BaseStorage:
    if kind == "memory":
        return MemoryStorage()
    return RedisStorage(redis=fakeredis_aioredis.FakeRedis(decode_responses=True))


@pytest.mark.parametrize("kind", ["memory", "redis"])
async def test_multistep_workflow(kind: str) -> None:
    storage = _storage(kind)
    dispatcher = Dispatcher(fsm_storage=storage)
    router = Router()
    collected: list[tuple[str, str]] = []

    @router.message(StateFilter(Incident.title))
    async def title(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(title=message.text)
        await state.set_state(Incident.severity)
        collected.append(("title", message.text))
        return "title-ok"

    @router.message(StateFilter(Incident.severity))
    async def severity(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(severity=message.text)
        await state.set_state(Incident.confirmation)
        collected.append(("severity", message.text))
        return "severity-ok"

    @router.message(StateFilter(Incident.confirmation))
    async def confirmation(message: MessageEvent, state: FSMContext) -> str:
        data = await state.get_data()
        await state.finish()
        collected.append(("confirmation", message.text))
        return f"done: {data['title']} {data['severity']} {message.text}"

    dispatcher.include_router(router)

    assert await dispatcher.feed_update(_message("first")) is None  # no state yet
    # The workflow starts outside the message stream (e.g. a slash command).
    await storage.set_state(
        StorageKey(user="users/1", space="spaces/A", thread=None),
        Incident.title.state,
    )
    assert await dispatcher.feed_update(_message("Bug")) == "title-ok"
    assert await dispatcher.feed_update(_message("high")) == "severity-ok"
    result = await dispatcher.feed_update(_message("confirm"))
    assert result == "done: Bug high confirm"
    assert collected == [
        ("title", "Bug"),
        ("severity", "high"),
        ("confirmation", "confirm"),
    ]
    assert await dispatcher.feed_update(_message("again")) is None
