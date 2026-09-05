"""Structured event lifecycle diagnostics."""

from __future__ import annotations

import json
import logging

import pytest

from chattice import Dispatcher, Router
from chattice.cards import Card
from chattice.events import ActionEvent
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import PubSubPullRunner
from tests.transports.test_pubsub_runner import FakePubSubMessage

_marker = logging.getLogger("test.marker")


async def test_handler_started_logged_before_invocation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router(name="start")

    @router.action("go")
    async def go(action: ActionEvent) -> None:
        del action
        _marker.info("INSIDE handler body")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.INFO, logger="chattice.routing")
    caplog.set_level(logging.INFO, logger="test.marker")

    await dispatcher.feed_update(ActionEvent(name="go"))

    messages = [record.getMessage() for record in caplog.records]
    started = next(i for i, m in enumerate(messages) if "handler_started:" in m)
    inside = next(i for i, m in enumerate(messages) if "INSIDE handler body" in m)
    completed = next(i for i, m in enumerate(messages) if "handler_completed:" in m)
    assert started < inside < completed


async def test_lifecycle_stages_emitted_for_handled_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router(name="start")

    @router.action("go")
    async def go(action: ActionEvent) -> None:
        del action

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.DEBUG, logger="chattice.routing")

    await dispatcher.feed_update(ActionEvent(name="go"))

    text = "\n".join(record.getMessage() for record in caplog.records)
    for stage in (
        "event received",
        "routing started",
        "handler_selected",
        "handler_started",
        "handler_completed",
    ):
        assert stage in text


def _action_payload(action: str) -> str:
    return json.dumps(
        {
            "type": "CARD_CLICKED",
            "user": {"name": "users/1"},
            "space": {"name": "spaces/A"},
            "message": {"name": "spaces/A/messages/M1", "sender": {"type": "BOT"}},
            "common": {"invokedFunction": action},
        }
    )


async def test_pubsub_delivery_stages_through_ack(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        bot=MockBot(),
    )
    caplog.set_level(logging.DEBUG, logger="chattice.pubsub")

    message = FakePubSubMessage(_action_payload("card.clicked"))
    await runner._handle(message)

    text = "\n".join(record.getMessage() for record in caplog.records)
    for stage in (
        "claim_started",
        "claim_result",
        "parsed",
        "answer_started",
        "answer_completed",
        "complete_started",
        "complete_succeeded",
        "acked",
    ):
        assert stage in text, f"missing stage {stage!r} in:\n{text}"
