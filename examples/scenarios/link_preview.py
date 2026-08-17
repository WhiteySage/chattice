"""Link preview: MESSAGE + matchedUrl -> UPDATE_USER_MESSAGE_CARDS.

When a Chat app has a URL pattern configured, Google sends a MESSAGE
event carrying message.matchedUrl; answering with a Card triggers the
documented UPDATE_USER_MESSAGE_CARDS response (the serializer selects it
from event.matched_url — never guessed).

Run:
    python examples/scenarios/link_preview.py
"""

from __future__ import annotations

import asyncio
from typing import cast

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import MessageEvent


async def _has_matched_url(event: object, context: object) -> bool:
    return isinstance(event, MessageEvent) and event.matched_url is not None


async def main() -> None:
    router = Router()

    @router.message(_has_matched_url)
    async def preview(message: MessageEvent) -> Card:
        assert message.matched_url
        ticket_id = message.matched_url.rsplit("/", 1)[-1]
        return Card(
            header=CardHeader(title=f"Ticket {ticket_id}"),
            sections=[Section(widgets=[TextParagraph("Предпросмотр заявки")])],
        )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payload = {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "message": {
            "name": "spaces/A/messages/2",
            "text": "https://example.com/ticket/42",
            "matchedUrl": {"url": "https://example.com/ticket/42"},
            "sender": {"type": "HUMAN"},
        },
    }
    card = await dispatcher.feed_update(parse_interaction(payload))
    print("preview card:", cast(Card, card).to_dict()["header"])


if __name__ == "__main__":
    asyncio.run(main())
