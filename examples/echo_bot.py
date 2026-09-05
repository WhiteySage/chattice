"""Echo bot over Pub/Sub streaming pull: copy, set YOUR env, run.

No domain, no TLS, no public IP — Google Chat delivers events into a
Pub/Sub topic and this process consumes the subscription; answers go
outbound through the authenticated Bot. No credentials are stored in
the repo: point the example at YOUR service account.

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
                                   (chat.bot + Pub/Sub Subscriber on the
                                   subscription)
    CHATTICE_SUBSCRIPTION          full pull subscription name,
                                   e.g. projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/echo_bot.py

Note: run_pubsub must receive bot=bot — the runner injects it into the
DI context; without it handlers get bot=None and replies never arrive.
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, Router
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

    @router.message()
    async def echo(message: MessageEvent) -> str:
        return f"You said: {message.text}"

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
