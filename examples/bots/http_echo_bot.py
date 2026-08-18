"""Minimal HTTP echo bot: Google Chat -> ngrok -> localhost:8000.

One handler: replies to any message with its text. Inbound verification
needs only the audience (your public HTTPS endpoint URL) — no secrets.

Environment:
    CHATTICE_AUDIENCE  your public HTTPS endpoint URL as set in the
                       Google Chat API Console (Connection settings ->
                       HTTP endpoint URL), e.g.
                       https://<ngrok-id>.ngrok-free.app

Optional (outbound/proactive replies):
    CHATTICE_SERVICE_ACCOUNT_FILE  path to the service-account JSON
                                   (chat.bot role)

Run:
    # terminal 1: expose localhost
    ngrok http 8000
    # terminal 2 (see scripts/serve_smoke.sh):
    #   scripts/serve_smoke.sh https://<ngrok-id>.ngrok-free.app \
    #       examples.bots.http_echo_bot:app
"""

from __future__ import annotations

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
