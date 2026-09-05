"""Error handling over Pub/Sub: copy, set YOUR env, run.

A handler that raises does not kill the runner: the error observer
receives an `ErrorEvent` and its return value goes to the user as the
answer. On a dispatcher WITHOUT an error observer the failure is nacked
(redelivery / poison-ACK per the documented terminal policy) and logged
safely — the raw exception text never reaches the chat.

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
    CHATTICE_SUBSCRIPTION          projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/error_handling.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, F, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import ErrorEvent, MessageEvent


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    router = Router()

    @router.message(F.argument_text == "boom")
    async def broken(message: MessageEvent) -> str:
        raise RuntimeError("simulated failure")

    @router.message(F.text)
    async def echo(message: MessageEvent) -> str:
        return f"You said: {message.text}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    @dispatcher.error()
    async def on_error(error: ErrorEvent) -> str:
        # The exception message may contain user data — send the CLASS,
        # not the text.
        return (
            f"Something went wrong ({type(error.exception).__name__}). Try again later."
        )

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
