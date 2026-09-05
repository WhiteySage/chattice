# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""Error pipeline: every failure stage leaves a visible, safe log."""

from __future__ import annotations

import json
import logging
from collections.abc import MutableMapping
from typing import NoReturn

import pytest

from chattice import Dispatcher, Router
from chattice.cards import Card
from chattice.events import ActionEvent, ErrorEvent, MessageEvent
from chattice.events.base import Event
from chattice.exceptions import DependencyResolutionError
from chattice.middleware import NextHandler
from chattice.testing import MockBot
from chattice.transports.pubsub_runner import PubSubPullRunner
from tests.transports.test_pubsub_runner import FailingStorage, FakePubSubMessage

_runtime = "chattice.runtime"
_pubsub = "chattice.pubsub"

SECRET = "SECRET_FORM_VALUE"


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


async def test_unhandled_handler_failure_logs_structured_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("boom")
    async def boom(action: ActionEvent) -> None:
        del action
        raise ValueError(SECRET)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.ERROR, logger=_runtime)

    with pytest.raises(ValueError, match=SECRET):
        await dispatcher.feed_update(ActionEvent(name="boom"))

    record = next(record for record in caplog.records if record.name == _runtime)
    message = record.getMessage()
    assert "handler failed" in message
    assert "event_type=action" in message
    assert "action=boom" in message
    assert "exception_type=ValueError" in message
    assert "stage=handler" in message
    assert "handler=" in message
    assert SECRET not in message
    assert record.exc_info is None  # production: no traceback by default


async def test_unhandled_failure_in_debug_mode_includes_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger(_runtime)
    logger.setLevel(logging.DEBUG)
    try:
        router = Router()

        @router.action("boom")
        async def boom(action: ActionEvent) -> None:
            del action
            raise ValueError(SECRET)

        dispatcher = Dispatcher()
        dispatcher.include_router(router)
        caplog.set_level(logging.DEBUG, logger=_runtime)

        with pytest.raises(ValueError, match=SECRET):
            await dispatcher.feed_update(ActionEvent(name="boom"))

        record = next(record for record in caplog.records if record.name == _runtime)
        assert record.exc_info is not None
        assert record.exc_info[0] is ValueError
        assert SECRET in caplog.text  # traceback is allowed in debug mode
    finally:
        logger.setLevel(logging.NOTSET)


async def test_filter_failure_reports_stage_filter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    async def bad_filter(event: object, data: object) -> bool:
        raise RuntimeError("filter boom")

    @router.message(bad_filter)
    async def handler(message: object) -> None:
        del message

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.ERROR, logger=_runtime)

    with pytest.raises(RuntimeError, match="filter boom"):
        await dispatcher.feed_update(MessageEvent(text="hi"))

    record = next(record for record in caplog.records if record.name == _runtime)
    assert "stage=filter" in record.getMessage()


async def test_dependency_resolution_failure_reports_stage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message()
    async def handler(missing_dependency: object) -> None:
        del missing_dependency

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.ERROR, logger=_runtime)

    with pytest.raises(DependencyResolutionError):
        await dispatcher.feed_update(MessageEvent(text="hi"))

    record = next(record for record in caplog.records if record.name == _runtime)
    assert "stage=dependency_resolution" in record.getMessage()


async def test_middleware_failure_reports_stage_middleware(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    class _BadMiddleware:
        async def __call__(
            self,
            handler: NextHandler,
            event: Event,
            data: MutableMapping[str, object],
        ) -> object:
            raise RuntimeError("middleware boom")

    @router.message()
    async def handler(message: object) -> None:
        del message

    router.middleware.register(_BadMiddleware())
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.ERROR, logger=_runtime)

    with pytest.raises(RuntimeError, match="middleware boom"):
        await dispatcher.feed_update(MessageEvent(text="hi"))

    record = next(record for record in caplog.records if record.name == _runtime)
    assert "stage=middleware" in record.getMessage()


async def test_error_handler_failure_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("boom")
    async def boom(action: ActionEvent) -> None:
        del action
        raise ValueError("original failure")

    @router.error()
    async def broken_error_handler(error: ErrorEvent) -> None:
        del error
        raise RuntimeError("error handler boom")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.ERROR, logger=_runtime)

    with pytest.raises(RuntimeError, match="error handler boom"):
        await dispatcher.feed_update(ActionEvent(name="boom"))

    assert any(
        "error handler failed" in record.getMessage()
        for record in caplog.records
        if record.name == _runtime
    )


class FailingUpdateBot(MockBot):
    async def update_message(
        self,
        name: str,
        text: str | None = None,
        *,
        card: object = None,
        timeout: float | None = None,
    ) -> NoReturn:
        raise RuntimeError("OUTBOUND-SECRET-DO-NOT-LOG")


async def test_outbound_update_failure_reports_stage(
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
        dispatcher, "projects/P/subscriptions/S", bot=FailingUpdateBot()
    )
    caplog.set_level(logging.ERROR, logger=_pubsub)

    message = FakePubSubMessage(_action_payload("card.clicked"))
    await runner._handle(message)

    assert message.nacked
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "outbound failed" in text
    assert "stage=outbound_update_message" in text
    assert "exception_type=RuntimeError" in text
    assert "OUTBOUND-SECRET" not in text


async def test_claim_failure_traceback_only_in_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        idempotency_storage=FailingStorage(fail_claim=True),
    )
    caplog.set_level(logging.ERROR, logger=_pubsub)

    message = FakePubSubMessage(json.dumps({"type": "MESSAGE"}))
    await runner._handle(message)

    record = next(
        record
        for record in caplog.records
        if record.name == _pubsub and "claim failed" in record.getMessage()
    )
    assert record.exc_info is None  # production: no traceback by default
    assert message.nacked


async def test_poison_ack_logs_exception_type_not_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.message()
    async def broken(message: MessageEvent) -> None:
        del message
        raise ValueError("POISON-SECRET-DO-NOT-LOG")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/S",
        bot=MockBot(),
        max_delivery_attempts=2,
    )
    caplog.set_level(logging.ERROR, logger=_pubsub)

    message = FakePubSubMessage(
        json.dumps(
            {
                "type": "MESSAGE",
                "message": {"text": "x"},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        ),
        delivery_attempt=2,
    )
    await runner._handle(message)

    assert message.acked  # terminal poison policy
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "poison message acked" in text
    assert "exception_type=ValueError" in text
    assert "POISON-SECRET" not in text
