# HTTP and Pub/Sub

The same interaction parser and `Dispatcher` sit behind both transports, but
their response capabilities are not interchangeable.

| Behavior | HTTP interactions | Pub/Sub push / streaming pull |
| --- | --- | --- |
| Delivery | HTTPS request | Pub/Sub message |
| Ack | HTTP response | 2xx push ack or subscriber ack |
| Synchronous text/card response | yes, within the interaction deadline | no |
| Dialog and App Home | yes, for eligible events | no |
| Outbound `Bot` calls | yes | yes |
| Return value over push | serialized to Chat | ignored (push) / mapped outbound where supported (pull runner) |

## HTTP

Use `create_chat_router(dispatcher, GoogleTokenVerifier(...))`. Verification is
fail-closed and failures return 401. Handler returns are serialized by event
type, including sender-sensitive card updates and HTTP-only dialogs/App Home.

## Pub/Sub push

Use `create_pubsub_router` with a `GooglePubSubVerifier`. Pub/Sub expects an
ack, not a Chat response, so handler results cannot answer the interaction.
Use an injected `Bot` for a later message or update. Failed deliveries can be
retried; make effects idempotent.

## Pub/Sub streaming pull

Install `chattice[pubsub]`. The full application is a long-lived process —
visually familiar if you come from aiogram's `start_polling`, but
technologically it is a persistent Pub/Sub subscriber stream with
acknowledgements and delivery attempts, NOT Telegram-style long polling
(Google Chat has no polling API):

```python
import asyncio
import os

from chattice import Dispatcher, Router
from chattice.client import Bot
from chattice.events import MessageEvent

router = Router()


@router.message()
async def hello(message: MessageEvent) -> None:
    await message.reply("Hello from Google Chat!")


async def main() -> None:
    bot = Bot(...)  # app-auth credentials
    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)

    await dispatcher.run_pubsub(os.environ["GOOGLE_CHAT_SUBSCRIPTION"], bot=bot)


if __name__ == "__main__":
    asyncio.run(main())
```

Run with `python app.py`. The method name is deliberately explicit:
`run_pubsub` names the concrete technology instead of hiding the transport
behind a generic `start()`. Dialog and App Home responses remain
unsupported on Pub/Sub.

Choose HTTP for interactive UI. Choose Pub/Sub when infrastructure policy or
behind-VPN consumption requires it and the application can respond through
authenticated Chat API calls.

Next: [Authentication and capabilities](auth-capabilities.md).

## Why Pub/Sub push when HTTP already has a public endpoint?

Push is a webhook with a durable queue in front of it:

- **Delivery guarantees** — if your endpoint is down, Pub/Sub buffers
  events (retries with backoff, dead-letter support) instead of losing
  them like a direct webhook eventually does.
- **At-least-once + duplicates** — Pub/Sub guarantees at-least-once
  delivery, so duplicates are normal; use the built-in idempotency
  storage in `create_pubsub_router`.
- **Backpressure** — the topic absorbs bursts; your endpoint does not
  have to keep up with the interaction deadline.
- **One topic, many consumers** — attach extra subscriptions (audit,
  analytics, a second bot) without touching the Chat configuration.
- **Serverless-friendly** — push works with Cloud Run/Functions that
  only serve HTTPS when called; pull requires a long-lived process.

Rule of thumb: HTTP for interactive UI (dialogs, synchronous card
updates); Pub/Sub push for durable delivery to a fragile/sleeping public
endpoint; Pub/Sub pull for no-public-endpoint deployments.

