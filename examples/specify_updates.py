"""Magic-filter routing over Pub/Sub: copy, set YOUR env, run.

Handlers register against predicate filters built with the `F` magic
object. The router picks the FIRST handler whose filter matches — exact
predicates go before broad ones, so "ping" is answered with "pong" and
everything else with the echo.

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
    CHATTICE_SUBSCRIPTION          projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/specify_updates.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, F, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import MessageEvent


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    router = Router()

    @router.message(F.argument_text == "ping")
    async def ping(message: MessageEvent) -> str:
        return "pong"

    @router.message(F.text)
    async def echo(message: MessageEvent) -> str:
        return f"echo: {message.text}"

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
