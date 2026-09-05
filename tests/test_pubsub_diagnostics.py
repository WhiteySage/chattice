"""Pub/Sub diagnostics: delivery identity, age, stale interactions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from chattice import Dispatcher, Router
from chattice.cards import Card
from chattice.events import ActionEvent
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import PubSubPullRunner
from tests.transports.test_pubsub_runner import FakePubSubMessage

_pubsub = "chattice.pubsub"


def _action_payload(
    action: str, *, event_time: str | None = None, message: str = "spaces/A/messages/M1"
) -> str:
    payload: dict[str, object] = {
        "type": "CARD_CLICKED",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "message": {"name": message, "sender": {"type": "BOT"}},
        "common": {"invokedFunction": action},
    }
    if event_time is not None:
        payload["eventTime"] = event_time
    return json.dumps(payload)


def _now_iso(offset_seconds: float = 0.0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset_seconds)).isoformat()


async def test_delivery_logs_identity_fields_and_kind_new(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.DEBUG, logger=_pubsub)

    message = FakePubSubMessage(
        _action_payload("card.clicked", event_time=_now_iso(-2)),
        message_id="m-42",
        delivery_attempt=0,
    )
    await runner._handle(message)

    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub and "delivery received" in record.getMessage()
    )
    text = record.getMessage()
    assert "pubsub_message_id=m-42" in text
    assert "delivery_attempt=0" in text
    assert "event_type=action" in text
    assert "action=card.clicked" in text
    assert "event_age_ms=" in text
    assert "message_resource_name=spaces/A/messages/M1" in text
    assert "space_resource_name=spaces/A" in text
    assert "delivery_kind=new" in text


async def test_redelivery_kind_for_positive_attempt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S")
    caplog.set_level(logging.DEBUG, logger=_pubsub)

    message = FakePubSubMessage(
        _action_payload("card.clicked", event_time=_now_iso()),
        delivery_attempt=2,
    )
    await runner._handle(message)

    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub and "delivery received" in record.getMessage()
    )
    assert "delivery_kind=redelivery" in record.getMessage()
    assert "delivery_attempt=2" in record.getMessage()


async def test_duplicate_completed_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.DEBUG, logger=_pubsub)

    message_id = "m-dup"
    await runner._handle(
        FakePubSubMessage(_action_payload("card.clicked"), message_id=message_id)
    )
    await runner._handle(
        FakePubSubMessage(_action_payload("card.clicked"), message_id=message_id)
    )

    duplicates = [
        record.getMessage()
        for record in caplog.records
        if record.name == _pubsub and "duplicate acked" in record.getMessage()
    ]
    assert len(duplicates) == 1
    assert "delivery_kind=duplicate_completed" in duplicates[0]


async def test_active_duplicate_kind_and_visible_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S")
    caplog.set_level(logging.DEBUG, logger=_pubsub)

    # Another owner is already processing this delivery.
    await runner._idempotency.claim(
        "projects/P/subscriptions/S:m-1", owner="someone-else", lease_seconds=300
    )
    message = FakePubSubMessage(_action_payload("card.clicked"), message_id="m-1")
    await runner._handle(message)

    assert message.nacked
    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub and "active duplicate" in record.getMessage()
    )
    assert "delivery_kind=active_duplicate" in record.getMessage()


async def test_delayed_interaction_warns_with_age(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.WARNING, logger=_pubsub)

    message = FakePubSubMessage(
        _action_payload("card.clicked", event_time=_now_iso(-60))
    )
    await runner._handle(message)

    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub
        and "delayed interaction received" in record.getMessage()
    )
    assert record.levelno == logging.WARNING
    assert "event_age_ms=" in record.getMessage()


async def test_stale_interaction_detected_but_processed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        calls.append(action.function_name)
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.WARNING, logger=_pubsub)

    newer = _now_iso(0)
    older = _now_iso(-600)
    # The NEWER interaction lands first, then the OLDER one from a backlog.
    # Different message_id -> two independent interactions.
    await runner._handle(
        FakePubSubMessage(
            _action_payload("card.clicked", event_time=newer), message_id="m-new"
        )
    )
    await runner._handle(
        FakePubSubMessage(
            _action_payload("card.clicked", event_time=older), message_id="m-old"
        )
    )

    # Business side effects must still run — stale events are NOT dropped.
    assert calls == ["card.clicked", "card.clicked"]
    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub
        and "stale interaction detected" in record.getMessage()
    )
    assert record.levelno == logging.WARNING
    assert "message=spaces/A/messages/M1" in record.getMessage()
    assert "latest_seen_event_time=" in record.getMessage()


async def test_missing_event_time_is_handled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.DEBUG, logger=_pubsub)

    message = FakePubSubMessage(_action_payload("card.clicked"))
    await runner._handle(message)

    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub and "delivery received" in record.getMessage()
    )
    text = record.getMessage()
    assert "event_age_ms=" not in text  # no invented values
    assert "delivery_kind=new" in text
    assert message.acked


async def test_future_event_time_does_not_crash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(dispatcher, "projects/P/subscriptions/S", bot=MockBot())
    caplog.set_level(logging.WARNING, logger=_pubsub)

    # Clock skew: a future timestamp must not warn nor crash.
    message = FakePubSubMessage(
        _action_payload("card.clicked", event_time=_now_iso(3600))
    )
    await runner._handle(message)

    assert message.acked
    assert not any(
        "delayed interaction received" in record.getMessage()
        for record in caplog.records
    )
