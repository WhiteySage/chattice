"""Workspace Events bot: CloudEvent -> workspace_event handler.

Parses a CloudEvents 1.0 envelope describing a Chat resource change with
`parse_workspace_event` and routes it into a `workspace_event` handler
filtered by the documented `google.workspace.chat.message.v1.created` type
(the same pipeline as pubsub_bot, over Workspace Events).

Run:
    python examples/bots/workspace_events_bot.py
"""

from __future__ import annotations

import asyncio

from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    WorkspaceEventType,
    parse_workspace_event,
)

_CLOUD_EVENT = {
    "specversion": "1.0",
    "id": "evt-1",
    "source": "//chat.googleapis.com/spaces/AAA",
    "type": WorkspaceEventType.MESSAGE_CREATED,
    "time": "2026-08-15T10:00:00Z",
    "subject": "spaces/AAA/messages/1",
    "data": {},
}


async def main() -> None:
    router = EventsRouter()

    @router.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
    async def on_message_created(event: WorkspaceEvent) -> str:
        return f"workspace cloud_type={event.cloud_type} subject={event.subject!r}"

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)

    result = await dispatcher.feed_event(parse_workspace_event(_CLOUD_EVENT))
    print(f"cloud event -> {result}")


if __name__ == "__main__":
    asyncio.run(main())
