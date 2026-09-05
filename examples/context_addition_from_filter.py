"""Context addition from filters over Pub/Sub: copy, set YOUR env, run.

A filter is not limited to True/False — it may return a mapping that is
merged into the dispatch context, and the framework injects those values
into the matching handler BY NAME (here: `topic`). Send
"topic: anything you like" and the handler answers with the queue
confirmation built from the injected value.

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
    CHATTICE_SUBSCRIPTION          projects/<p>/subscriptions/<s>

Run:
    pip install "chattice[pubsub]"
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
    python examples/context_addition_from_filter.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import Event, MessageEvent


async def extract_topic(event: Event, context: object) -> bool | dict[str, object]:
    del context
    if not isinstance(event, MessageEvent):
        return False
    text = event.argument_text or ""
    if not text.startswith("topic:"):
        return False
    return {"topic": text.removeprefix("topic:").strip()}


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    router = Router()

    @router.message(extract_topic)
    async def queue_topic(message: MessageEvent, topic: str) -> str:
        return f"Queued: {topic}"

    @router.message()
    async def fallback(message: MessageEvent) -> str:
        return "Send 'topic: <something>' to see context injection."

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
