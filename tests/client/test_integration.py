"""Phase gate: receive an interaction and perform an asynchronous send."""

from __future__ import annotations

from collections.abc import MutableMapping

import httpx
from fastapi import FastAPI
from google.auth.credentials import AnonymousCredentials

from chattice import Dispatcher, Router
from chattice.client import Bot
from chattice.events import Event, MessageEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.middleware import BaseMiddleware, NextHandler
from chattice.transports.http import InteractionResponse, MockVerifier

from ._fake_transport import FakeChatTransport


class InjectBot(BaseMiddleware):
    """Middleware making the bot available to handlers via DI by name."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def __call__(
        self,
        handler: NextHandler,
        event: Event,
        data: MutableMapping[str, object],
    ) -> object:
        data.setdefault("bot", self._bot)
        return await handler(event, data)


def _message_payload(text: str) -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": text},
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
    }


async def test_interaction_to_bot_send_full_path() -> None:
    creds = AnonymousCredentials()  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(credentials=creds)
    bot = Bot(credentials=creds, transport=transport)
    router = Router()
    router.middleware.register(InjectBot(bot))

    @router.message()
    async def on_message(
        message: MessageEvent, bot: Bot, response: InteractionResponse
    ) -> None:
        assert message.space is not None
        sent = await bot.send_message(message.space, text=message.text)
        response.respond(sent.text)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.json() == {"text": "ping"}
    request = transport.requests[-1]
    assert request.parent == "spaces/AAA"
    assert request.message.text == "ping"
