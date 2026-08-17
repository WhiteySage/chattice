"""Distinguishability gate: interaction and resource runtimes never mix."""

from __future__ import annotations

import base64
import json

import pytest

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import MessageEvent
from chattice.transports.pubsub import PubSubPushAdapter
from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    parse_workspace_event,
)


def _interaction() -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
    }


async def test_three_ingresses_do_not_mix() -> None:
    router = EventsRouter()
    kinds: list[str] = []

    interaction_router = Router()

    @interaction_router.message()
    async def interaction(message: MessageEvent) -> str:
        kinds.append("interaction")
        return "sync-ok"

    @router.workspace_event()
    async def resource(event: WorkspaceEvent) -> None:
        kinds.append("workspace")

    dispatcher = Dispatcher()
    dispatcher.include_router(interaction_router)
    events_dispatcher = EventsDispatcher()
    events_dispatcher.include_router(router)

    direct = await dispatcher.feed_update(parse_interaction(_interaction()))
    assert direct == "sync-ok"

    envelope = {
        "message": {
            "data": base64.b64encode(json.dumps(_interaction()).encode()).decode(),
            "messageId": "m-1",
        },
        "subscription": "projects/p/subscriptions/s",
    }
    pubsub_event = PubSubPushAdapter().parse_envelope(envelope)
    assert isinstance(pubsub_event, MessageEvent)
    pubsub_result = await dispatcher.feed_update(pubsub_event)
    assert pubsub_result == "sync-ok"

    workspace = parse_workspace_event(
        {
            "specversion": "1.0",
            "id": "evt-1",
            "source": "//chat.googleapis.com/spaces/AAA",
            "type": "google.workspace.chat.message.v1.created",
            "time": "2026-08-15T10:00:00Z",
            "data": {},
        }
    )
    assert isinstance(workspace, WorkspaceEvent)
    with pytest.raises(TypeError, match="Event instances"):
        await dispatcher.feed_update(workspace)  # type: ignore[arg-type]
    await events_dispatcher.feed_event(workspace)
    with pytest.raises(TypeError, match="WorkspaceEvent"):
        await events_dispatcher.feed_event(
            parse_interaction(_interaction())  # type: ignore[arg-type]
        )

    assert kinds == ["interaction", "interaction", "workspace"]
