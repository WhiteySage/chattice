"""Echo bot over Pub/Sub streaming pull: copy, set env, run.

No domain, no TLS, no public IP — Google Chat delivers events into a
Pub/Sub topic and this process consumes the subscription (persistent
subscriber stream, not Telegram-style polling). Responses go outbound
through the authenticated Bot; there is no synchronous response channel
on pull (no Dialogs, no App Home).

Environment:
    GOOGLE_CHAT_SUBSCRIPTION       full pull subscription name,
                                   e.g. projects/<p>/subscriptions/<s>
    CHATTICE_SERVICE_ACCOUNT_FILE  path to the service account JSON
                                   (roles: Pub/Sub Subscriber on the
                                   subscription + chat.bot)

Run:
    python examples/bots/pubsub_pull_echo_bot.py
"""

from __future__ import annotations

import asyncio
import os

from chattice import Dispatcher, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import MessageEvent

router = Router()


@router.message()
async def echo(message: MessageEvent) -> None:
    await message.reply(f"You said: {message.text}")


async def main() -> None:
    bot = Bot(
        credentials_provider=(
            ServiceAccountCredentialsProvider.from_service_account_file(
                os.environ["CHATTICE_SERVICE_ACCOUNT_FILE"]
            )
        )
    )
    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)
    await dispatcher.run_pubsub(os.environ["GOOGLE_CHAT_SUBSCRIPTION"])


if __name__ == "__main__":
    asyncio.run(main())
