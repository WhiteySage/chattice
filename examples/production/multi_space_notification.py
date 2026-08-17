"""Proactive multi-Space business send — the core outbound use case.

ONE business event, ONE Bot identity, MULTIPLE target Spaces, NO inbound
interaction:

    CRM creates a request
        ->
    Python application
        ->
    bot.send_message(space=FINANCE_SPACE, card=request_card)
        ->
    bot.send_message(space=MANAGERS_SPACE, card=request_card)

Same shape as ``aiogram Bot.send_message(chat_id=...)`` but with
Google-native Space semantics. No NotificationService, no event bus, no
queue: explicit outbound sends are the whole feature. A real deployment
uses Bot with app credentials and Space memberships; this example runs
on the testing MockBot with no network.

Run:
    uv run python examples/production/multi_space_notification.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from chattice.cards import Card, CardHeader, Section, TextParagraph
from chattice.events import SpaceRef
from chattice.testing import MockBot

FINANCE_SPACE = SpaceRef(name="spaces/FINANCE")
MANAGERS_SPACE = SpaceRef(name="spaces/MANAGERS")


@dataclass
class CRMClient:
    """Business service — knows NOTHING about Google Chat."""

    requests: list[dict[str, str]] = field(default_factory=list)

    async def create_request(self, data: dict[str, str]) -> str:
        self.requests.append(data)
        return f"REQ-{len(self.requests):03d}"


def request_card(request_id: str, data: dict[str, str]) -> Card:
    return Card(
        header=CardHeader(title=f"{request_id}: {data['category']}"),
        sections=[Section(widgets=[TextParagraph(str(data))])],
    )


async def on_business_event(crm: CRMClient, bot: MockBot) -> None:
    """The application-level handler for one business event."""
    data = {"category": "hardware", "priority": "high", "details": "Ноутбук"}
    request_id = await crm.create_request(data)
    card = request_card(request_id, data)
    # ONE event -> TWO Spaces, same Bot identity:
    await bot.send_message(FINANCE_SPACE, text="", card=card)
    await bot.send_message(MANAGERS_SPACE, text="", card=card)


async def main() -> None:
    crm = CRMClient()
    bot = MockBot()
    await on_business_event(crm, bot)
    targets = [call[1]["space"] for call in bot.calls]
    print("business event ->", targets)
    print("crm stored:", crm.requests)


if __name__ == "__main__":
    asyncio.run(main())
