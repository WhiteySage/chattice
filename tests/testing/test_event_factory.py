"""EventFactory typed builders."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.events import (
    ActionEvent,
    AddedToSpaceEvent,
    AppHomeEvent,
    FormSubmitEvent,
    MessageEvent,
    RemovedFromSpaceEvent,
    UnknownEvent,
)
from chattice.testing import EventFactory
from chattice.workspace_events import WorkspaceEvent, WorkspaceEventType


def test_message_builder() -> None:
    event = EventFactory.message("ping")
    assert isinstance(event, MessageEvent)
    assert event.text == "ping"
    assert event.actor is not None
    assert event.space is not None


def test_action_builder() -> None:
    event = EventFactory.action("deploy.confirm", parameters={"env": "prod"})
    assert isinstance(event, ActionEvent)
    assert event.function_name == "deploy.confirm"
    assert dict(event.parameters) == {"env": "prod"}


def test_added_removed_builders() -> None:
    added = EventFactory.added_to_space()
    assert isinstance(added, AddedToSpaceEvent)
    removed = EventFactory.removed_from_space()
    assert isinstance(removed, RemovedFromSpaceEvent)


def test_app_home_and_form_builders() -> None:
    assert isinstance(EventFactory.app_home(), AppHomeEvent)
    assert isinstance(EventFactory.form_submit("update.home"), FormSubmitEvent)


def test_workspace_event_builder() -> None:
    event = EventFactory.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
    assert isinstance(event, WorkspaceEvent)
    assert event.cloud_type == WorkspaceEventType.MESSAGE_CREATED
    assert event.event_id == "evt-test"


def test_unknown_builder() -> None:
    assert isinstance(EventFactory.unknown_event("FUTURE"), UnknownEvent)


async def test_round_trip_through_dispatcher() -> None:
    router = Router()
    seen: list[str] = []

    @router.message()
    async def handler(message: MessageEvent) -> str:
        seen.append(message.text)
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(EventFactory.message("ping"))
    assert result == "ok"
    assert seen == ["ping"]
