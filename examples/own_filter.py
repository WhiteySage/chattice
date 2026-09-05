"""Own filters over Pub/Sub: copy, set YOUR env, run.

Any async callable `(event, context) -> bool` works as a filter. The
first matching handler wins; a bare `@router.message()` handler acts as
the fallback when no own filter matched.

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
    CHATTICE_SUBSCRIPTION          projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/own_filter.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import Event, MessageEvent


async def is_question(event: Event, context: object) -> bool:
    del context
    return isinstance(event, MessageEvent) and (event.argument_text or "").endswith("?")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    router = Router()

    @router.message(is_question)
    async def answer(message: MessageEvent) -> str:
        return "Thinking... ask me later, I am just an example."

    @router.message()
    async def fallback(message: MessageEvent) -> str:
        return f"Echo: {message.text}"

    dispatcher = Dispatcher()
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
