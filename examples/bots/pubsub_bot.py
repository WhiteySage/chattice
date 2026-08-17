"""Pub/Sub bot: push envelope -> decoded interaction -> message handler.

Builds a documented Pub/Sub push envelope by base64-encoding a Chat
interaction JSON into message.data, decodes it with PubSubPushAdapter, and
feeds the resulting event through a message handler.
Over a real push endpoint the response would be a 204 ack — the handler
return value is only shown here.

Run:
    python examples/bots/pubsub_bot.py
"""

from __future__ import annotations

import asyncio
import base64
import json

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.transports.pubsub import PubSubPushAdapter


def _pubsub_envelope() -> dict[str, object]:
    interaction = {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
    }
    data = base64.b64encode(json.dumps(interaction).encode()).decode()
    return {
        "message": {
            "data": data,
            "messageId": "m-1",
            "publishTime": "2026-08-15T10:00:00.123Z",
        },
        "subscription": "projects/p/subscriptions/s",
    }


async def main() -> None:
    router = Router()

    @router.message()
    async def on_message(message: MessageEvent) -> str:
        return f"message text={message.text!r}"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    envelope = _pubsub_envelope()
    event = PubSubPushAdapter().parse_envelope(envelope)
    result = await dispatcher.feed_update(event)
    print(f"pubsub envelope -> {result}")


if __name__ == "__main__":
    asyncio.run(main())
