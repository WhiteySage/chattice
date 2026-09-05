"""Finite state machine over Pub/Sub: copy, set YOUR env, run.

A three-step Incident workflow driven by ordinary messages: send
"incident" to start, then answer with the title, the severity, and
"confirm". State lives in MemoryStorage (swap in RedisStorage for
restarts — same interface).

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
    CHATTICE_SUBSCRIPTION          projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/finite_state_machine.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, F, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import MessageEvent
from chattice.fsm import FSMContext, MemoryStorage, State, StateFilter, StatesGroup


class Incident(StatesGroup):
    title = State()
    severity = State()
    confirmation = State()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    router = Router()

    @router.message(F.argument_text == "incident")
    async def start(message: MessageEvent, state: FSMContext) -> str:
        await state.set_state(Incident.title)
        return "Incident report started. Send the incident TITLE."

    @router.message(StateFilter(Incident.title))
    async def title(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(title=message.argument_text)
        await state.set_state(Incident.severity)
        return "Got the title. Now the SEVERITY (low / medium / high)."

    @router.message(StateFilter(Incident.severity))
    async def severity(message: MessageEvent, state: FSMContext) -> str:
        if message.argument_text not in {"low", "medium", "high"}:
            return "Choose low, medium, or high."
        await state.update_data(severity=message.argument_text)
        await state.set_state(Incident.confirmation)
        return "Got the severity. Send 'confirm' to finish."

    @router.message(StateFilter(Incident.confirmation))
    async def confirmation(message: MessageEvent, state: FSMContext) -> str:
        if message.argument_text != "confirm":
            return "Send 'confirm' to finish."
        data = await state.get_data()
        await state.finish()
        return f"Done: {data['title']} ({data['severity']}) — {message.argument_text}"

    dispatcher = Dispatcher(fsm_storage=MemoryStorage())
    dispatcher.include_router(router)
    service_account_file = _require_env("CHATTICE_SERVICE_ACCOUNT_FILE")
    app_credentials = ServiceAccountCredentialsProvider.from_service_account_file(
        service_account_file
    )
    pull_credentials = ServiceAccountCredentialsProvider.from_service_account_file(
        service_account_file, scopes=["https://www.googleapis.com/auth/pubsub"]
    )
    async with Bot(app_credentials_provider=app_credentials) as bot:
        await dispatcher.run_pubsub(
            _require_env("CHATTICE_SUBSCRIPTION"),
            bot=bot,
            credentials_provider=pull_credentials,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
