"""FastAPI bot: the HTTP interaction endpoint wired into an ASGI app.

This module builds `app` at import time — the exact object uvicorn serves.
`main()` is a no-op runner kept for the uniform bot contract (import, then
run). It deliberately does NOT start uvicorn; run the server with:

    uv run --extra fastapi uvicorn examples.bots.fastapi_bot:app --port 8000

Then POST a documented interaction payload to http://localhost:8000/.
The MockVerifier is for local development only — production must use
GoogleTokenVerifier(audience=...) per the official verification docs.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import InteractionResponse, MockVerifier

router = Router()


@router.message()
async def echo(message: MessageEvent, response: InteractionResponse) -> None:
    response.respond(message.text)


dispatcher = Dispatcher()
dispatcher.include_router(router)

app = FastAPI()
app.include_router(create_chat_router(dispatcher, MockVerifier()))


async def main() -> None:
    print(
        "fastapi_bot: app is built; serve it with "
        "'uv run --extra fastapi uvicorn examples.bots.fastapi_bot:app --port 8000'"
    )


if __name__ == "__main__":
    asyncio.run(main())
