"""Registration (FSM version): aiogram-style sequential message flow.

The migration-friendly version: one message per field, state remembered
durably in FSM storage (survives restarts with Redis). The Google-native
alternative lives in registration_dialog.py — one dialog collects the
same fields in a single interaction (forms collect data).

Run:
    python examples/scenarios/registration_fsm.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import CommandEvent, Event, MessageEvent
from chattice.fsm import FSMContext, MemoryStorage, StateFilter
from chattice.fsm.states import State, StatesGroup

CANCEL_WORDS = {"отмена", "cancel"}


class Registration(StatesGroup):
    name = State()
    email = State()
    department = State()
    confirm = State()


def _message(text: str) -> Event:
    return parse_interaction(
        {
            "type": "MESSAGE",
            "eventTime": "2026-08-15T10:00:00Z",
            "message": {"text": text},
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
        }
    )


def build_dispatcher(storage: MemoryStorage | None = None) -> Dispatcher:
    storage = storage or MemoryStorage()  # RedisStorage for durable restarts
    router = Router()

    @router.command()
    async def start_registration(event: CommandEvent, state: FSMContext) -> str:
        await state.set_state(Registration.name)
        return "Как вас зовут?"

    @router.message(StateFilter(Registration.name))
    async def name(message: MessageEvent, state: FSMContext) -> str:
        if message.text.lower() in CANCEL_WORDS:
            await state.finish()
            return "Регистрация отменена."
        await state.update_data(name=message.text)
        await state.set_state(Registration.email)
        return "Ваш email?"

    @router.message(StateFilter(Registration.email))
    async def email(message: MessageEvent, state: FSMContext) -> str:
        if message.text.lower() in CANCEL_WORDS:
            await state.finish()
            return "Регистрация отменена."
        await state.update_data(email=message.text)
        await state.set_state(Registration.department)
        return "Отдел? (sales / support)"

    @router.message(StateFilter(Registration.department))
    async def department(message: MessageEvent, state: FSMContext) -> str:
        if message.text.lower() in CANCEL_WORDS:
            await state.finish()
            return "Регистрация отменена."
        await state.update_data(department=message.text)
        await state.set_state(Registration.confirm)
        data = await state.get_data()
        return (
            f"Подтвердите: {data['name']} · {data['email']} · {message.text} (да/нет)"
        )

    @router.message(StateFilter(Registration.confirm))
    async def confirm(message: MessageEvent, state: FSMContext) -> str:
        if message.text.lower() in ("да", "yes"):
            data = await state.get_data()
            await state.finish()
            return f"Готово: {data['name']} <{data['email']}> в {data['department']}"
        await state.set_state(Registration.name)
        return "Начнём заново. Как вас зовут?"

    dispatcher = Dispatcher(fsm_storage=storage)
    dispatcher.include_router(router)
    return dispatcher


async def main() -> None:
    storage = MemoryStorage()
    dispatcher = build_dispatcher(storage)
    seed = {
        "type": "APP_COMMAND",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "appCommandMetadata": {"appCommandId": 1, "appCommandType": "QUICK_COMMAND"},
    }
    await dispatcher.feed_update(parse_interaction(seed))  # -> name state
    for answer in ("Иван", "ivan@example.com", "sales", "да"):
        print(await dispatcher.feed_update(_message(answer)))
    # restart simulation: a SECOND dispatcher over the SAME storage
    # continues the durable flow where the first one stopped
    restarted = build_dispatcher(storage)
    print("post-restart flow:", await restarted.feed_update(_message("нет")))


if __name__ == "__main__":
    asyncio.run(main())
