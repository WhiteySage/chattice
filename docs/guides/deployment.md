# Production & deployment

## Minimal FastAPI deployment

```python
from fastapi import FastAPI

from chattice import Dispatcher
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import GoogleTokenVerifier

dispatcher = Dispatcher()
# ...routers...

app = FastAPI()
app.include_router(
    create_chat_router(dispatcher, GoogleTokenVerifier(audience="https://your.domain/"))
)
```

Run with any ASGI server:

```bash
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

## Push deployments (Pub/Sub)

```python
from chattice.integrations.fastapi import create_pubsub_router
from chattice.idempotency import RedisIdempotencyStorage
from chattice.transports.pubsub import GooglePubSubVerifier

app.include_router(
    create_pubsub_router(
        dispatcher,
        verifier=GooglePubSubVerifier(
            audience="https://your.domain/pubsub",
            service_account_email="push@project.iam.gserviceaccount.com",
        ),
        idempotency_storage=RedisIdempotencyStorage(),  # from chattice.idempotency
    )
)
```

Push constraints: ack-only (204/429/500), no dialogs, no sync card
updates — update cards via `bot.update_message(card=...)` afterwards.

## Resource lifecycle

```python
async with Bot(credentials_provider=...) as bot, dispatcher.lifespan(resource):
    ...
```

`Bot.close()` awaits the real transport closer; the lifespan closes
every resource even when one closer fails.

## Configuration checklist

1. Chat app in **Live** mode; app added to the target Spaces.
2. App auth (service account, `chat.bot`) for outbound sends; accessory
   widgets and private viewer are app-auth-only.
3. HTTP endpoint audience matches the verifier configuration.
4. Push: OIDC service-account identity configured and verified.
5. Durable state on Redis, never `MemoryStorage` in production.
6. Handlers answer interactions within the 30 s deadline; long work via
   `Bot` calls.

## Multi-instance notes

- Pub/Sub dedupe keys are namespaced by subscription; the idempotency
  state machine (claim/complete/release, 429 on active) is safe across
  instances sharing one Redis.
- FSM records use compare-and-set — concurrent instances surface
  conflicts instead of losing updates.
