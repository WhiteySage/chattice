"""Router diagnostics: path identifiers and duplicate-name warning."""

from __future__ import annotations

import logging

import pytest

from chattice import Dispatcher, Router
from chattice.events import ActionEvent

_routing = "chattice.routing"


async def test_router_paths_are_indexed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router(name="same"))
    dispatcher.include_router(Router(name="same"))

    @dispatcher._children[1].action("go")
    async def go(action: ActionEvent) -> None:
        del action

    caplog.set_level(logging.DEBUG, logger=_routing)

    await dispatcher.feed_update(ActionEvent(name="go"))

    text = "\n".join(record.getMessage() for record in caplog.records)
    # The dispatcher itself is router[0]; the second included router is router[2].
    assert "router_path=router[2]" in text


async def test_duplicate_router_name_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router(name="start"))
    caplog.set_level(logging.WARNING, logger=_routing)

    dispatcher.include_router(Router(name="start"))

    assert any(
        "duplicate router name" in record.getMessage() for record in caplog.records
    )
