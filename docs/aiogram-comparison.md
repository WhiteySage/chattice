# aiogram comparison

For developers coming from [aiogram](https://docs.aiogram.dev/), chattice is an
async Python framework for Google Chat — not a Telegram-compatible reimplementation.
This is a semantic comparison of concepts, not a compatibility promise. Every
chattice claim below is grounded in the shipped API; where Google Chat lacks a
Telegram feature, this page says so explicitly.

| aiogram concept | chattice concept | Google Chat limitation |
| --- | --- | --- |
| `chat_id` | `SpaceRef`/`ThreadRef` resource names (`events.references`) | Spaces are the addressing unit, identified by resource names like `spaces/AAA...`; direct messages are spaces too |
| `update_id` | no update IDs | No documented update ordering API; ordering is not guaranteed |
| inline queries | not implemented | No Google Chat equivalent |
| `callback_data` | button action `function` name + string parameters (`cards.Action`) | Action parameters are string key/value pairs; no opaque callback payload |
| `message.answer()` | handler return, `MessageEvent.reply()`, `ThreadRef.send()`, `SpaceRef.send()`, or `Bot.send_message()` | A sync HTTP response and an authenticated Chat API call are different channels |
| reply keyboard | Cards (buttons) (`cards`) | Cards can only be updated via `updateMessage` for messages the bot created |
| dialogs anywhere | dialogs open only in response to an interaction (`OPEN_DIALOG`) | Dialogs are visible only to the user who triggered the interaction |
| polling | HTTP push / Pub/Sub push ingress + Pub/Sub STREAMING PULL | No Telegram-style long polling; streaming pull is a persistent subscriber stream with Pub/Sub's own ACK protocol (see [pubsub](architecture/pubsub.md)) |
| FSM `chat_id` keys | `StorageKey(user, space, thread)` (`fsm.storage`) | Keys are Google resource references, never chat IDs |

## What you keep from aiogram

The developer experience that made aiogram productive carries over:

- **Routers** — feature-scoped handler registration on a shared `Dispatcher`.
- **Magic filters** — the `F` predicate DSL, reimplemented over Google-native
  fields (no Telegram fields leak into it).
- **Middleware** — `Dispatcher`/`Router` middleware with the same
  outer-to-inner ordering semantics.
- **Dependency injection** — context-injected handlers; the
  `InteractionContext` (request snapshot, response, sync deadline) is injected
  like aiogram's per-event context.
- **FSM** — `StatesGroup`, `StateFilter`, memory/Redis storage, and
  `StorageKey`-based scoping (`USER_IN_SPACE`, `USER`, `SPACE`).

The ergonomics survive; the event vocabulary does not.

## What Google Chat simply does not have

The following Telegram concepts have **no Google Chat equivalent**, and
chattice does not pretend they exist:

- **Inline queries** — nothing like Telegram's inline mode.
- **Update ordering** — no `update_id`-style sequence and no documented ordering
  guarantee, so no `update_id`-based deduplication.
- **Telegram-style long polling** — no `getUpdates`-style polling. Ingress is push (HTTP webhook / Pub/Sub push) or Pub/Sub STREAMING PULL (`dispatcher.run_pubsub`), which is a persistent subscriber stream, not a polling loop.
- **User-updatable messages** — cards can be edited via `updateMessage`, but only
  if the bot created the message.
- **Context menus / global dialogs** — dialogs only open in direct response to an
  interaction and are visible only to the opener.

Where a Telegram feature has no Google Chat counterpart, the honest answer is
"not available", not a reimplementation with a different name.

## Proactive sends: chat_id vs Space

AIOGRAM:

```python
await bot.send_message(chat_id=FINANCE_CHAT, text="New request #431")
```

CHATTICE:

```python
await bot.send_message(space=FINANCE_SPACE, text="New request #431")
```

Multi-target (ONE business event → SEVERAL Spaces):

AIOGRAM:

```python
await bot.send_message(chat_id=A, text=...)
await bot.send_message(chat_id=B, text=...)
```

CHATTICE:

```python
await bot.send_message(space=A, text=...)
await bot.send_message(space=B, text=...)
```

Business logic (CRM, APIs, databases, screenshot/report generation,
Jira/Asana) does NOT know about Google Chat in either framework — only
the messenger-facing calls change. See
`examples/production/multi_space_notification.py`.

## The reply mental model

Chattice provides contextual send methods without hiding Google's two
channels. A handler return is the current interaction response; contextual and
imperative send methods use the authenticated Chat API:

```python
return "pong"  # interaction response
await message.reply("pong")  # authenticated reply in the known thread
await message.thread.send("pong")  # authenticated explicit thread send
await message.space.send("pong")  # authenticated Space-level send
await bot.send_message("spaces/AAA", text="pong")  # imperative outbound
```

The contextual methods are zero-fetch adapters over the same bound `Bot`.


**Mention routing note:** Google's `argumentText` keeps
the SPACE after the stripped app mention — a Space message
`@AppName ping` arrives as `text="@AppName ping"`,
`argument_text=" ping"`. Strip before comparing
(`(message.argument_text or "").strip() == "ping"`) — see
`examples/smoke_http.py`.

## The same skeleton, two transports

Your aiogram echo bot:

```python
from aiogram import Bot, Dispatcher
from aiogram.types import Message

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message()
async def echo(message: Message) -> None:
    await message.answer(message.text)


async def main() -> None:
    await dp.start_polling(bot)
```

Chattice, **HTTP** (Google calls your HTTPS endpoint; the handler RETURN
is the synchronous response):

```python
import os
from fastapi import FastAPI
from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import GoogleTokenVerifier

router = Router()


@router.message()
async def echo(message: MessageEvent) -> str:
    return f"You said: {message.text}"  # synchronous response, no auth


dispatcher = Dispatcher()
dispatcher.include_router(router)

app = FastAPI()
app.include_router(
    create_chat_router(
        dispatcher,
        GoogleTokenVerifier(audience=os.environ["CHATTICE_AUDIENCE"]),
    )
)
# python -m uvicorn app:app --port 8000
```

Chattice, **Pub/Sub streaming pull** (persistent runner, like
`start_polling` in shape; no domain, no TLS):

```python
import asyncio
import os
from chattice import Dispatcher, Router
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot
from chattice.events import MessageEvent

router = Router()


@router.message()
async def echo(message: MessageEvent) -> None:
    await message.reply(f"You said: {message.text}")  # no sync return on pull


async def main() -> None:
    bot = Bot(
        credentials_provider=ServiceAccountCredentialsProvider.from_service_account_file(
            os.environ["CHATTICE_SERVICE_ACCOUNT_FILE"]
        )
    )
    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)
    await dispatcher.run_pubsub(os.environ["GOOGLE_CHAT_SUBSCRIPTION"])


if __name__ == "__main__":
    asyncio.run(main())
# python app.py
```

Correspondences: `start_polling(bot)` ↔ `run_pubsub(subscription)` (the
Bot binds at `Dispatcher(bot=...)` or `run_pubsub(..., bot=bot)`);
aiogram webhook ↔ the HTTP variant above. Note: handlers always attach
to a `Router`, then `dispatcher.include_router(router)` — `@dp.message()`
does not exist on the Chattice Dispatcher.

