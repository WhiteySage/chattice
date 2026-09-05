"""Echo bot behind an HTTP webhook: copy, set YOUR env, serve.

Google Chat POSTs interactions to YOUR public HTTPS endpoint; the
handler RETURN is the synchronous response. Incoming calls are verified
fail-closed against YOUR audience — no verification bypass in the example.

Environment (yours, not committed anywhere):

    CHATTICE_AUDIENCE              YOUR Authentication Audience: the
                                   endpoint URL or the project number

Run:
    pip install "chattice[fastapi]" uvicorn
    export CHATTICE_AUDIENCE=https://your-endpoint.example.com
    python -m uvicorn examples.echo_bot_webhook:app --port 8000
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import GoogleTokenVerifier, InteractionResponse


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before serving this example")
    return value


router = Router()


@router.message()
async def echo(message: MessageEvent, response: InteractionResponse) -> None:
    response.respond(f"You said: {message.text}")


dispatcher = Dispatcher()
dispatcher.include_router(router)

app = FastAPI()
app.include_router(
    create_chat_router(
        dispatcher,
        GoogleTokenVerifier(audience=_require_env("CHATTICE_AUDIENCE")),
    )
)


async def main() -> None:
    print(
        "echo_bot_webhook: serve it with "
        "'python -m uvicorn examples.echo_bot_webhook:app --port 8000'"
    )


if __name__ == "__main__":
    asyncio.run(main())
