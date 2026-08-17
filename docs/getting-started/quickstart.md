# 5-minute Quickstart

```bash
python -m pip install "chattice[fastapi]" uvicorn
```

This app answers any Google Chat message synchronously. It uses the actual
public API: `Dispatcher` is the application event engine, `Router` owns
handlers, and the FastAPI integration exposes the HTTPS endpoint.

## 1. Create `app.py`

```python
import os

from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import GoogleTokenVerifier

router = Router()


@router.message()
async def hello(message: MessageEvent) -> str:
    return "Hello from Google Chat!"


dispatcher = Dispatcher()
dispatcher.include_router(router)

app = FastAPI()
app.include_router(
    create_chat_router(
        dispatcher,
        GoogleTokenVerifier(audience=os.environ["CHATTICE_AUDIENCE"]),
    )
)
```

Returning a string is the synchronous response to the current interaction. It
does not make a Chat API call and must complete within Google's interaction
deadline (30 seconds). Outbound `Bot` calls are a separate, authenticated
channel.

The webhook endpoint is mounted at the root path `/` by default; pass
`path="..."` to `create_chat_router(...)` to serve it elsewhere.

## 2. Run it

Choose the same audience value that you will select in the Chat API
configuration: either the exact public HTTPS endpoint URL or the Cloud project
number.

```bash
export CHATTICE_AUDIENCE="https://chat.example.com/"
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# with uv
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

The endpoint must be publicly reachable over HTTPS before Google Chat can call
it. For local development, use an HTTPS tunnel tool (ngrok, cloudflared, or
similar) and set both the configuration URL and `CHATTICE_AUDIENCE` to that
exact public URL. If you forget to export `CHATTICE_AUDIENCE`, the app fails at
startup with `KeyError: 'CHATTICE_AUDIENCE'` — set the variable and run again.
Never use `MockVerifier` on an endpoint reachable by Google or other users; it
is only for isolated tests.

## 3. Configure and try it

Follow [Create/configure a Google Chat app](google-chat-setup.md), choose the
HTTP endpoint, save the app, then open a direct message with it or add it to a
test Space. Send `hello`; the response is `Hello from Google Chat!`.

In a shared Space, Chat normally invokes the app when mentioned or through a
configured command. Direct messages are their own Spaces.

## 4. Verify without Google credentials

The repository's `examples/docs/from_zero.py` runs the same parser and
dispatcher plus replies, Threads, commands, buttons, forms, dialogs, private
messages, and Workspace Events using the public `MockBot`. This is a framework
test, not a request-verification bypass:

```bash
python examples/docs/from_zero.py
```

Expected output:

```text
documentation journey OK
```

Next: [Configure Google Chat](google-chat-setup.md).
