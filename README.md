<img src="https://raw.githubusercontent.com/WhiteySage/chattice/main/docs/assets/brand/chattice-logo.png"
     alt="Chattice" width="320" />

# Chattice

Async, typed event framework for Google Chat apps — aiogram-quality DX, Google-native semantics.

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/chattice/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-public%20beta-orange)](#status)
[![Discussions](https://img.shields.io/badge/discussions-questions%20%26%20help-blue)](https://github.com/WhiteySage/chattice/discussions)

```python
from chattice import Dispatcher, F, Router
from chattice.events import MessageEvent

router = Router()


@router.message(F.text == "ping")
async def ping(message: MessageEvent) -> str:
    return "pong"  # synchronous interaction response (no auth, 30 s deadline)


dispatcher = Dispatcher()
dispatcher.include_router(router)
```

## What this is

- **Google Chat-native.** Space, Thread, Message, Command, Action, Card,
  Dialog, App Home, Workspace Events are first-class typed objects. No
  Telegram concepts leak into the domain model.
- **aiogram ergonomics.** Routers, magic filters (`F`), middleware,
  dependency injection, FSM — the DX you know, without Telegram
  semantics.
- **Explicit response model.** A handler RETURN is the synchronous
  interaction response (30 s deadline); outbound `Bot` calls are
  separate authenticated operations. Contextual `message.reply()` /
  `thread.send()` / `space.send()` methods are zero-fetch adapters over
  that same Bot, never a hidden second channel.
- **Secure by default.** Incoming verification is fail-closed, push
  endpoints require a verifier, outbound privacy gates (private
  messages, notifications, preview features) fail closed before any
  network call.
- **Core is small.** Core abstracts Google Chat platform primitives and
  technical boilerplate ONLY. Business scenarios (polls, approvals,
  tickets) are assembled from the primitives in your
  application code — never added to core.

## What this is not

- **Not a Telegram framework.** No `chat_id`, no `CallbackQuery`, no
  `Update` hierarchy, no Telegram-style long polling (see the
  [aiogram comparison](https://whiteysage.github.io/chattice/aiogram-comparison/)).
- **Not a Google product.** Independent open-source project, not
  endorsed by Google.

## Two ways to run

Chattice has two honest startup models (see the
[aiogram side-by-side](docs/aiogram-comparison.md)):

```python
# HTTP — Google calls your HTTPS endpoint; the handler RETURN is the
# synchronous response (Dialogs and App Home work here).
app.include_router(create_chat_router(dispatcher, GoogleTokenVerifier(audience=...)))
# python -m uvicorn app:app

# Pub/Sub streaming pull — a persistent subscriber process, visually
# like aiogram's start_polling, but it is NOT Telegram polling.
# No domain/TLS needed; no Dialogs, no App Home — answers go outbound
# through the authenticated Bot.
await dispatcher.run_pubsub(subscription, bot=bot)
# python app.py
```

## Capabilities

| Area | Support |
| --- | --- |
| Events | MESSAGE, CARD_CLICKED, APP_COMMAND (slash/quick/message actions), ADDED/REMOVED_FROM_SPACE, APP_HOME, SUBMIT_FORM, WIDGET_UPDATED |
| Routing | Routers, observers, magic filters, middleware, DI |
| Cards | Typed facades (buttons, forms, validation), sync updates (UPDATE_MESSAGE / UPDATE_USER_MESSAGE_CARDS, sender-derived) |
| Dialogs | OPEN_DIALOG, submit/cancel observers, action status; capability-gated per transport |
| FSM | State/StatesGroup, Memory + Redis record storage (compare-and-set) |
| Ingress | HTTP (verified), Pub/Sub push (verified), Pub/Sub streaming pull, Workspace Events CloudEvents |
| Auth | App (service account), user (OAuth refresh), incoming verification |
| Testing | MockBot, EventFactory, assertions, fake transport |

## Install

Python 3.11+ (3.11–3.13 tested). MIT-licensed.

```bash
pip install "chattice[fastapi,pubsub,redis]"  # core + all integrations

# or pick only what you need:
#   pip install chattice            core
#   pip install "chattice[fastapi]" FastAPI integration
#   pip install "chattice[redis]"   Redis FSM/idempotency storage
#   pip install "chattice[pubsub]"  Pub/Sub push + streaming pull

# using uv
uv add "chattice[fastapi,pubsub,redis]"
```

## Quickstart

1. Parse a documented interaction payload:

```python
from chattice.adapters.google_chat import parse_interaction

event = parse_interaction(payload)
result = await dispatcher.feed_update(event)
```

2. Serve HTTP interactions (FastAPI):

```python
from fastapi import FastAPI
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import GoogleTokenVerifier

app = FastAPI()
app.include_router(create_chat_router(dispatcher, GoogleTokenVerifier(audience="...")))
```

3. Send messages:

```python
from chattice.client import Bot

bot = Bot(credentials=...)
await bot.send_message("spaces/AAA", text="hello")
```

Inside an interaction handler, configure the same Bot once and use the known
Google context without extra fetches:

```python
dispatcher = Dispatcher(bot=bot)


@router.message()
async def reply(message: MessageEvent) -> None:
    await message.reply("hello in this thread")
```

## Docs

Start with [Installation](https://whiteysage.github.io/chattice/getting-started/installation/), the
[5-minute Quickstart](https://whiteysage.github.io/chattice/getting-started/quickstart/), and the
[Space → Thread → Message mental model](https://whiteysage.github.io/chattice/concepts/mental-model/). The
[public API reference](https://whiteysage.github.io/chattice/public-api/), [Google mapping](https://whiteysage.github.io/chattice/reference/google-api-mapping/),
and [aiogram comparison](https://whiteysage.github.io/chattice/aiogram-comparison/) are linked from the docs site.
Runnable examples live in [`examples/`](https://github.com/WhiteySage/chattice/tree/main/examples); LLM agents get
[`llms.txt`](https://whiteysage.github.io/chattice/llms.txt).

## Status

Pre-1.0 **public beta** (current version 0.14.0b4) — see
[CHANGELOG](CHANGELOG.md). The documented stable beta
surface is frozen: pre-1.0 work may add APIs but does not incompatibly
rename, remove, or change existing contracts. `chattice.experimental`
has no compatibility promise. `Bot.raw_client` and raw event payloads
follow Google's SDK and wire schema rather than the stable facade
promise. **Not an official Google product** — independent open-source
software, not endorsed by Google. MIT License, see [LICENSE](https://github.com/WhiteySage/chattice/blob/main/LICENSE).
