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


## VPS recipe (Caddy + systemd)

A complete deployment on a single VPS with a domain (`chat.example.com`),
TLS termination, and process supervision.

1. **Install:**

   ```bash
   sudo apt install -y python3.12-venv caddy
   sudo adduser --system --home /opt/echo-bot --shell /usr/sbin/nologin echo-bot
   sudo -u echo-bot -H python3.12 -m venv /opt/echo-bot/.venv
   sudo -u echo-bot -H /opt/echo-bot/.venv/bin/pip install "chattice[fastapi]" uvicorn
   ```

2. **App** (`/opt/echo-bot/app.py`) — same shape as the Quickstart, plus a
   health check:

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
    return f"You said: {message.text}"


dispatcher = Dispatcher()
dispatcher.include_router(router)

app = FastAPI()
app.include_router(
    create_chat_router(
        dispatcher,
        GoogleTokenVerifier(audience=os.environ["CHATTICE_AUDIENCE"]),
    )
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
```

3. **systemd unit** (`/etc/systemd/system/echo-bot.service`):

   ```ini
   [Unit]
   Description=Chattice echo bot
   After=network-online.target

   [Service]
   User=echo-bot
   WorkingDirectory=/opt/echo-bot
   Environment=CHATTICE_AUDIENCE=https://chat.example.com/
   ExecStart=/opt/echo-bot/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
   Restart=on-failure
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable --now echo-bot
   ```

4. **TLS termination — Caddy** (`/etc/caddy/Caddyfile`):

   ```
   chat.example.com {
       reverse_proxy 127.0.0.1:8000
   }
   ```

   Caddy obtains and renews the Let's Encrypt certificate automatically;
   nginx + certbot works equally well.

5. **Verify:** `curl https://chat.example.com/healthz` → 200, then set the
   app to Live mode in the Console and send a message from a test Space.
   Follow `journalctl -u echo-bot -f`; a 401 means an audience mismatch.

Keep `CHATTICE_AUDIENCE` EXACTLY equal to the endpoint URL configured in
the Chat API Console (trailing slash included).

## VPS recipe — Pub/Sub pull (no domain, no TLS, no public IP)

With streaming pull Google does NOT call your server: events flow
Chat → Pub/Sub → your persistent subscriber. The VPS only needs outbound
access (works behind a VPN; no domain, no Caddy, no `CHATTICE_AUDIENCE`).

```python
# app.py
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
    await dispatcher.run_pubsub(os.environ["GOOGLE_CHAT_SUBSCRIPTION"], bot=bot)


if __name__ == "__main__":
    asyncio.run(main())
```

```ini
# /etc/systemd/system/echo-bot.service
[Unit]
Description=Chattice echo bot (Pub/Sub pull)
After=network-online.target

[Service]
User=echo-bot
WorkingDirectory=/opt/echo-bot
Environment=GOOGLE_CHAT_SUBSCRIPTION=projects/<project>/subscriptions/<sub>
Environment=CHATTICE_SERVICE_ACCOUNT_FILE=/opt/echo-bot/sa.json
ExecStart=/opt/echo-bot/.venv/bin/python app.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Trade-offs: no synchronous interaction responses, no Dialogs, no
App Home — handlers act through authenticated `Bot` calls.

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
