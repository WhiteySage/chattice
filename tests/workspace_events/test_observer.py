"""workspace_event observer routing."""

from __future__ import annotations

from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    WorkspaceEventType,
    parse_workspace_event,
)


def _event(cloud_type: str = WorkspaceEventType.MESSAGE_CREATED) -> WorkspaceEvent:
    return parse_workspace_event(
        {
            "specversion": "1.0",
            "id": "evt-1",
            "source": "//chat.googleapis.com/spaces/AAA",
            "type": cloud_type,
            "time": "2026-08-15T10:00:00Z",
            "data": {},
        }
    )


async def test_typed_observer_matches() -> None:
    router = EventsRouter()
    seen: list[str] = []

    @router.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
    async def on_created(event: WorkspaceEvent) -> str:
        seen.append(event.cloud_type)
        return "handled"

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_event(_event())
    assert result == "handled"
    assert seen == [WorkspaceEventType.MESSAGE_CREATED]


async def test_typed_observer_does_not_match_other_types() -> None:
    router = EventsRouter()
    seen: list[str] = []

    @router.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
    async def on_created(event: WorkspaceEvent) -> str:
        seen.append(event.cloud_type)
        return "handled"

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_event(_event(WorkspaceEventType.SPACE_UPDATED))
    assert result is None
    assert seen == []


async def test_generic_fallback() -> None:
    router = EventsRouter()
    seen: list[str] = []

    @router.workspace_event()
    async def any_event(event: WorkspaceEvent) -> str:
        seen.append(event.cloud_type)
        return "any"

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_event(_event(WorkspaceEventType.SPACE_UPDATED))
    assert result == "any"
