"""Runtime diagnostics: handler/outbound latency split, thresholds."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from chattice import Dispatcher, Router
from chattice.cards import Card
from chattice.events import ActionEvent
from chattice.observability import RuntimeDiagnostics
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import PubSubPullRunner
from tests.transports.test_pubsub_runner import FakePubSubMessage

_runtime = "chattice.runtime"
_pubsub = "chattice.pubsub"


def _action_payload(action: str, *, event_time: str | None = None) -> str:
    payload: dict[str, object] = {
        "type": "CARD_CLICKED",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "message": {"name": "spaces/A/messages/M1", "sender": {"type": "BOT"}},
        "common": {"invokedFunction": action},
    }
    if event_time is not None:
        payload["eventTime"] = event_time
    return json.dumps(payload)


def _now_iso(offset_seconds: float = 0.0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset_seconds)).isoformat()


async def test_ack_log_splits_handler_and_outbound_latency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        await asyncio.sleep(0.01)
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
        if record.name == _pubsub and "acked:" in record.getMessage()
    )
    text = record.getMessage()
    assert "handler_duration_ms=" in text
    assert "outbound_operation=update_message" in text
    assert "outbound_duration_ms=" in text
    assert "total_duration_ms=" in text


async def test_slow_handler_warns_above_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("slow")
    async def slow(action: ActionEvent) -> None:
        del action
        await asyncio.sleep(0.02)

    dispatcher = Dispatcher(runtime_diagnostics=RuntimeDiagnostics(slow_handler_ms=0.0))
    dispatcher.include_router(router)
    caplog.set_level(logging.WARNING, logger=_runtime)

    await dispatcher.feed_update(ActionEvent(name="slow"))

    record = next(
        record
        for record in caplog.records
        if record.name == _runtime and "slow handler" in record.getMessage()
    )
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert "handler=" in message
    assert "duration_ms=" in message


async def test_fast_handler_does_not_warn_by_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("fast")
    async def fast(action: ActionEvent) -> None:
        del action

    dispatcher = Dispatcher()  # default slow_handler_ms=1000
    dispatcher.include_router(router)
    caplog.set_level(logging.WARNING, logger=_runtime)

    await dispatcher.feed_update(ActionEvent(name="fast"))

    assert not any("slow handler" in record.getMessage() for record in caplog.records)


async def test_slow_handler_warning_disabled_with_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("slow")
    async def slow(action: ActionEvent) -> None:
        del action
        await asyncio.sleep(0.02)

    dispatcher = Dispatcher(
        runtime_diagnostics=RuntimeDiagnostics(slow_handler_ms=None)
    )
    dispatcher.include_router(router)
    caplog.set_level(logging.WARNING, logger=_runtime)

    await dispatcher.feed_update(ActionEvent(name="slow"))

    assert not any("slow handler" in record.getMessage() for record in caplog.records)


async def test_delayed_event_threshold_is_configurable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("card.clicked")
    async def clicked(action: ActionEvent) -> Card:
        del action
        return Card()

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    # A very strict threshold: any age above 0 warns.
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        bot=MockBot(),
        delayed_event_ms=0.0,
    )
    caplog.set_level(logging.WARNING, logger=_pubsub)

    message = FakePubSubMessage(
        _action_payload("card.clicked", event_time=_now_iso(-10))
    )
    await runner._handle(message)

    assert any(
        "delayed interaction received" in record.getMessage()
        for record in caplog.records
    )


async def test_delayed_event_warning_disabled_with_none(
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
        delayed_event_ms=None,
    )
    caplog.set_level(logging.WARNING, logger=_pubsub)

    message = FakePubSubMessage(_action_payload("card.clicked"))
    await runner._handle(message)

    assert not any(
        "delayed interaction received" in record.getMessage()
        for record in caplog.records
    )
