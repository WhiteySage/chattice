"""Simple text triggers: exact / prefix / contains / compound (no FSM).

The aiogram-developer bread-and-butter, kept extremely simple.

Run:
    python examples/scenarios/text_triggers.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, F, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import MessageEvent


def _message(text: str) -> MessageEvent:
    from typing import cast

    return cast(
        MessageEvent,
        parse_interaction(
            {
                "type": "MESSAGE",
                "message": {"text": text},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        ),
    )


async def main() -> None:
    router = Router()

    @router.message(F.text == "ping")
    async def ping(message: MessageEvent) -> str:
        return "pong"

    @router.message(F.text == "привет")
    async def hello_exact(message: MessageEvent) -> str:
        return "пока"

    @router.message(F.text.startswith("привет"))
    async def hello_prefix(message: MessageEvent) -> str:
        return "пока (по префиксу)"

    @router.message(F.text.startswith("ticket"))
    async def ticket_prefix(message: MessageEvent) -> str:
        return f"ticket prefix: {message.text}"

    @router.message(F.text.contains("отчет"))
    async def report_related(message: MessageEvent) -> str:
        return "релевантно отчетам"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    for text in ("ping", "привет ПК", "ticket-42 сломан", "квартальный отчет готов"):
        print(text, "->", await dispatcher.feed_update(_message(text)))


if __name__ == "__main__":
    asyncio.run(main())
