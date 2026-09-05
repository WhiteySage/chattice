"""Unmatched interactive events are visible; strict mode fails early."""

from __future__ import annotations

import logging

import pytest

from chattice import Dispatcher, Router
from chattice.events import ActionEvent, CommandEvent, MessageEvent, MessageRef
from chattice.exceptions import UnhandledInteractionError

_routing = "chattice.routing"


async def test_unmatched_action_emits_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router(name="start"))
    caplog.set_level(logging.WARNING, logger=_routing)

    result = await dispatcher.feed_update(
        ActionEvent(name="start_main", message=MessageRef(name="spaces/A/messages/M9"))
    )

    assert result is None  # ordinary mode: no raise, spinner just gets nothing
    record = next(
        record
        for record in caplog.records
        if record.name == _routing and "unhandled interaction" in record.getMessage()
    )
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert "event_type=action" in message
    assert "action=start_main" in message
    assert "message=spaces/A/messages/M9" in message


async def test_unmatched_command_emits_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    caplog.set_level(logging.WARNING, logger=_routing)

    await dispatcher.feed_update(CommandEvent(command_id=7))

    record = next(
        record
        for record in caplog.records
        if record.name == _routing and "unhandled command" in record.getMessage()
    )
    assert record.levelno == logging.WARNING
    assert "command_id=7" in record.getMessage()


async def test_unmatched_generic_event_stays_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    caplog.set_level(logging.DEBUG, logger=_routing)

    await dispatcher.feed_update(MessageEvent(text="hi"))

    warnings = [
        record
        for record in caplog.records
        if record.name == _routing and record.levelno >= logging.WARNING
    ]
    assert warnings == []
    assert any("no handler matched" in record.getMessage() for record in caplog.records)


async def test_strict_mode_raises_on_unmatched_action() -> None:
    dispatcher = Dispatcher(strict_interactions=True)
    dispatcher.include_router(Router())

    with pytest.raises(UnhandledInteractionError):
        await dispatcher.feed_update(ActionEvent(name="start_main"))


async def test_strict_mode_raises_on_unmatched_command() -> None:
    dispatcher = Dispatcher(strict_interactions=True)
    dispatcher.include_router(Router())

    with pytest.raises(UnhandledInteractionError):
        await dispatcher.feed_update(CommandEvent(command_id=7))


async def test_registered_actions_listed_in_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = Router()

    @router.action("start_alpha")
    async def alpha(action: ActionEvent) -> None:
        del action

    @router.action("start_beta")
    async def beta(action: ActionEvent) -> None:
        del action

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    caplog.set_level(logging.DEBUG, logger=_routing)

    await dispatcher.feed_update(ActionEvent(name="start_unknown"))

    listing = next(
        record.getMessage()
        for record in caplog.records
        if record.name == _routing and "registered actions" in record.getMessage()
    )
    assert "start_alpha" in listing
    assert "start_beta" in listing
