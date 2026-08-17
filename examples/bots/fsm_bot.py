"""FSM bot: multi-step Incident workflow on MemoryStorage (no network).

Drives an Incident report through three states (title -> severity ->
confirmation) with `StateFilter` + `FSMContext`, backed by `MemoryStorage`.
The workflow starts outside the message stream (a slash command seeds the
first state), then every step is routed statefully and `finish()` closes the
workflow (mirroring tests/fsm/test_gate.py).

Run:
    python examples/bots/fsm_bot.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import Event, MessageEvent
from chattice.fsm import FSMContext, MemoryStorage, StateFilter, StorageKey
from chattice.fsm.states import State, StatesGroup


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


async def main() -> None:
    storage = MemoryStorage()
    router = Router()

    @router.message(StateFilter(Incident.title))
    async def title(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(title=message.text)
        await state.set_state(Incident.severity)
        return "title-ok"

    @router.message(StateFilter(Incident.severity))
    async def severity(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(severity=message.text)
        await state.set_state(Incident.confirmation)
        return "severity-ok"

    @router.message(StateFilter(Incident.confirmation))
    async def confirmation(message: MessageEvent, state: FSMContext) -> str:
        data = await state.get_data()
        await state.finish()
        return f"done: {data['title']} {data['severity']} {message.text}"

    dispatcher = Dispatcher(fsm_storage=storage)
    dispatcher.include_router(router)

    # No state yet: the message cannot match any StateFilter.
    print("before workflow:", await dispatcher.feed_update(_message("first")))

    # The workflow starts outside the message stream, e.g. a /incident command.
    await storage.set_state(
        StorageKey(user="users/1", space="spaces/A", thread=None),
        Incident.title.state,
    )

    print("title step:   ", await dispatcher.feed_update(_message("Bug")))
    print("severity step:", await dispatcher.feed_update(_message("high")))
    print("confirm step: ", await dispatcher.feed_update(_message("confirm")))

    # finish() removed the record: the stateful filters match nothing again.
    print("after finish: ", await dispatcher.feed_update(_message("again")))


if __name__ == "__main__":
    asyncio.run(main())
