"""Pub/Sub and Workspace Events push routers (ASGI)."""

from __future__ import annotations

import base64
import json

import httpx
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.integrations.fastapi import (
    create_pubsub_router,
    create_workspace_events_router,
)
from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
)


def _interaction() -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
    }


def _pubsub_body() -> dict[str, object]:
    raw = json.dumps(_interaction()).encode()
    return {
        "message": {"data": base64.b64encode(raw).decode(), "messageId": "m-1"},
        "subscription": "projects/p/subscriptions/s",
    }


def _cloudevent() -> dict[str, object]:
    return {
        "specversion": "1.0",
        "id": "evt-1",
        "source": "//chat.googleapis.com/spaces/AAA",
        "type": "google.workspace.chat.message.v1.created",
        "time": "2026-08-15T10:00:00Z",
        "data": {},
    }


def _workspace_envelope(
    *, attributes: dict[str, str] | None = None, data: object | None = None
) -> dict[str, object]:
    """The OFFICIAL Workspace Events Pub/Sub binding (ce-* in attributes,
    resource data in base64 message.data)."""
    if attributes is None:
        attributes = {
            "ce-id": "evt-1",
            "ce-source": "//chat.googleapis.com/spaces/AAA",
            "ce-specversion": "1.0",
            "ce-time": "2026-08-15T10:00:00Z",
            "ce-type": "google.workspace.chat.message.v1.created",
        }
    if data is None:
        data = {"message": {"name": "spaces/AAA/messages/B"}}
    raw = json.dumps(data).encode()
    return {
        "message": {
            "data": base64.b64encode(raw).decode(),
            "messageId": "m-2",
            "attributes": attributes,
        },
        "subscription": "projects/p/subscriptions/s",
    }


async def test_pubsub_push_acks_204_and_ignores_result() -> None:
    router = Router()

    @router.message()
    async def echo(message: MessageEvent) -> str:
        return "must-be-ignored"  # no sync response over Pub/Sub

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_pubsub_router(dispatcher, allow_unverified=True))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_pubsub_body())
    assert result.status_code == 204
    assert result.content == b""


async def test_pubsub_malformed_returns_400() -> None:
    app = FastAPI()
    app.include_router(create_pubsub_router(Dispatcher(), allow_unverified=True))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json={"message": {}})
    assert result.status_code == 400


async def test_workspace_events_push_acks_204() -> None:
    router = EventsRouter()
    seen: list[str] = []

    @router.workspace_event()
    async def handler(event: WorkspaceEvent) -> None:
        seen.append(event.event_id)

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(dispatcher, allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json=_workspace_envelope())
    assert result.status_code == 204
    assert seen == ["evt-1"]


async def test_workspace_events_envelope_data_reaches_handler() -> None:
    router = EventsRouter()
    seen: list[object] = []

    @router.workspace_event()
    async def handler(event: WorkspaceEvent) -> None:
        seen.append(dict(event.data))

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(dispatcher, allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json=_workspace_envelope())
    assert result.status_code == 204
    assert seen == [{"message": {"name": "spaces/AAA/messages/B"}}]


async def test_workspace_events_malformed_returns_400() -> None:
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json={"message": {}})
    assert result.status_code == 400


async def test_workspace_events_envelope_without_attributes_returns_400() -> None:
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    raw = json.dumps({"message": {"name": "spaces/AAA/messages/B"}}).encode()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/workspace-events",
            json={
                "message": {
                    "data": base64.b64encode(raw).decode(),
                    "messageId": "m-2",
                },
                "subscription": "projects/p/subscriptions/s",
            },
        )
    assert result.status_code == 400


async def test_workspace_events_envelope_wrong_specversion_returns_400() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "0.3",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/workspace-events", json=_workspace_envelope(attributes=attributes)
        )
    assert result.status_code == 400


async def test_interaction_on_workspace_endpoint_returns_400() -> None:
    """Cross-ingress: a Chat interaction is NOT a Workspace push envelope."""
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json=_interaction())
    assert result.status_code == 400


async def test_cloudevent_on_pubsub_endpoint_returns_400() -> None:
    """Cross-ingress: a raw CloudEvent is NOT a Pub/Sub push envelope."""
    app = FastAPI()
    app.include_router(create_pubsub_router(Dispatcher(), allow_unverified=True))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_cloudevent())
    assert result.status_code == 400


async def test_structured_cloudevent_on_workspace_endpoint_returns_400() -> None:
    """Google has no HTTPS delivery mode for Workspace Events: a structured
    CloudEvent POSTed directly (the fabricated pre-fix mode) is rejected.
    parse_workspace_event() remains available for OFFLINE use only."""
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json=_cloudevent())
    assert result.status_code == 400


async def test_workspace_lifecycle_envelope_acknowledged() -> None:
    """Lifecycle events (subscription expired/suspended) use a different
    source (workspaceevents.googleapis.com) and type namespace."""
    attributes = {
        "ce-id": "evt-l",
        "ce-source": "//workspaceevents.googleapis.com/subscriptions/SUB",
        "ce-specversion": "1.0",
        "ce-time": "2026-08-15T10:00:00Z",
        "ce-type": "google.workspace.events.subscription.v1.expired",
    }
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(EventsDispatcher(), allow_unverified=True)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/workspace-events",
            json=_workspace_envelope(
                attributes=attributes,
                data={"subscription": {"name": "subscriptions/SUB"}},
            ),
        )
    assert result.status_code == 204


async def test_workspace_duplicate_message_id_absorbed() -> None:
    from chattice.idempotency import MemoryIdempotencyStorage

    router = EventsRouter()
    seen = 0

    @router.workspace_event()
    async def handler(event: WorkspaceEvent) -> None:
        nonlocal seen
        seen += 1

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=MemoryIdempotencyStorage(),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/workspace-events", json=_workspace_envelope())
        second = await client.post("/workspace-events", json=_workspace_envelope())
    assert first.status_code == 204
    assert second.status_code == 204
    assert seen == 1


async def test_workspace_handler_failure_releases_claim() -> None:
    from chattice.idempotency import MemoryIdempotencyStorage

    router = EventsRouter()
    attempts = 0

    @router.workspace_event()
    async def handler(event: WorkspaceEvent) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("first attempt fails")

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=MemoryIdempotencyStorage(),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/workspace-events", json=_workspace_envelope())
        redelivered = await client.post("/workspace-events", json=_workspace_envelope())
    assert first.status_code == 500
    assert redelivered.status_code == 204
    assert attempts == 2


# --- Push verification (A4): secure by default ---


async def test_push_router_requires_verifier_or_opt_in() -> None:
    from chattice.integrations.fastapi import create_pubsub_router

    try:
        create_pubsub_router(Dispatcher())
    except ValueError as error:
        assert "verification" in str(error)
    else:
        raise AssertionError("expected ValueError without verifier/opt-in")


async def test_push_router_verifier_rejects_before_dispatch() -> None:
    from chattice.transports.pubsub import MockPubSubVerifier

    router = Router()
    seen = 0

    @router.message()
    async def handler(message: MessageEvent) -> str:
        nonlocal seen
        seen += 1
        return "x"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_pubsub_router(dispatcher, verifier=MockPubSubVerifier(reject=True))
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_pubsub_body())
    assert result.status_code == 401
    assert seen == 0  # body was never parsed nor dispatched


async def test_push_router_verifier_accepts_valid_request() -> None:
    from chattice.transports.pubsub import MockPubSubVerifier

    router = Router()
    seen = 0

    @router.message()
    async def handler(message: MessageEvent) -> str:
        nonlocal seen
        seen += 1
        return "x"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_pubsub_router(dispatcher, verifier=MockPubSubVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_pubsub_body())
    assert result.status_code == 204
    assert seen == 1


async def test_workspace_router_verifier_rejects_before_dispatch() -> None:
    from chattice.transports.pubsub import MockPubSubVerifier

    router = EventsRouter()
    seen: list[str] = []

    @router.workspace_event()
    async def handler(event: WorkspaceEvent) -> None:
        seen.append(event.event_id)

    dispatcher = EventsDispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(
            dispatcher, verifier=MockPubSubVerifier(reject=True)
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/workspace-events", json=_workspace_envelope())
    assert result.status_code == 401
    assert seen == []
