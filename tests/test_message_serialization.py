# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""Per-message concurrency control: one card, one update at a time."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from chattice import Dispatcher, Router
from chattice.cards import Card
from chattice.events import ActionEvent
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import PubSubPullRunner
from tests.transports.test_pubsub_runner import FakePubSubMessage

_pubsub = "chattice.pubsub"


def _action_payload(action: str, message: str) -> str:
    return json.dumps(
        {
            "type": "CARD_CLICKED",
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
            "message": {"name": message, "sender": {"type": "BOT"}},
            "common": {"invokedFunction": action},
        }
    )


class TrackingBot(MockBot):
    """Records how many update_message calls overlap in time."""

    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.max_active = 0

    async def update_message(
        self,
        name: str,
        text: str | None = None,
        *,
        card: object = None,
        timeout: float | None = None,
    ) -> Any:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1


def _make_runner(bot: MockBot) -> tuple[PubSubPullRunner, Dispatcher]:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher, "projects/P/subscriptions/S", bot=bot, max_concurrency=10
    )
    return runner, dispatcher


async def test_same_message_updates_are_serialized() -> None:
    bot = TrackingBot()
    runner, _ = _make_runner(bot)
    payload = _action_payload("card.clicked", "spaces/A/messages/M1")

    await asyncio.gather(
        runner._handle(FakePubSubMessage(payload, message_id="m-1")),
        runner._handle(FakePubSubMessage(payload, message_id="m-2")),
        runner._handle(FakePubSubMessage(payload, message_id="m-3")),
    )

    assert bot.max_active == 1


async def test_different_messages_update_in_parallel() -> None:
    bot = TrackingBot()
    runner, _ = _make_runner(bot)

    await asyncio.gather(
        runner._handle(
            FakePubSubMessage(
                _action_payload("card.clicked", "spaces/A/messages/M1"),
                message_id="m-1",
            )
        ),
        runner._handle(
            FakePubSubMessage(
                _action_payload("card.clicked", "spaces/A/messages/M2"),
                message_id="m-2",
            )
        ),
    )

    assert bot.max_active == 2


async def test_lock_registry_cleans_up_after_unique_keys() -> None:
    bot = MockBot()
    runner, _ = _make_runner(bot)

    for index in range(1000):
        message_name = f"spaces/A/messages/M{index}"
        await runner._handle(
            FakePubSubMessage(
                _action_payload("card.clicked", message_name),
                message_id=f"m-{index}",
            )
        )

    assert runner._update_locks._locks == {}
    assert runner._update_locks._waiters == {}
