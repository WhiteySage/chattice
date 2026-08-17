"""F02 regression: boundary parse failures never leak payloads into logs.

Each probe plants a unique secret sentinel in an untrusted payload and
asserts the sentinel reaches NEITHER any log record NOR the response
body — while the stable fields (error class, path) remain logged.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.integrations.fastapi import (
    create_chat_router,
    create_pubsub_router,
    create_workspace_events_router,
)
from chattice.transports.http import MockVerifier
from chattice.workspace_events import EventsDispatcher


def _sentinel_logs(caplog: pytest.LogCaptureFixture) -> str:
    records = caplog.records
    parts: list[str] = []
    for record in records:
        parts.append(record.getMessage())
        parts.append(json.dumps(record.args, default=str))
    return "\n".join(parts)


def _dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(Router())
    return dispatcher


def _events_dispatcher() -> EventsDispatcher:
    return EventsDispatcher()


async def _post(
    app: FastAPI, url: str, content: bytes, headers: dict[str, str]
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(url, content=content, headers=headers)


async def test_invalid_interaction_payload_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.include_router(create_chat_router(_dispatcher(), MockVerifier()))
    sentinel = "SECRET-INTERACTION-9911"
    body = json.dumps(
        {
            "type": "MESSAGE",
            "common": {"formInputs": sentinel},  # not a dict -> parse error
            "message": {"text": sentinel},
        }
    ).encode()
    result = await _post(app, "/", body, {"content-type": "application/json"})
    assert result.status_code == 400
    assert sentinel not in result.text
    assert sentinel not in _sentinel_logs(caplog)


async def test_pubsub_non_json_redacted(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()
    app.include_router(create_pubsub_router(_dispatcher(), allow_unverified=True))
    sentinel = "SECRET-PUBSUB-JSON-9911"
    result = await _post(
        app, "/pubsub", f"not json {sentinel}".encode(), {"content-type": "text/plain"}
    )
    assert result.status_code == 400
    assert sentinel not in result.text
    assert sentinel not in _sentinel_logs(caplog)


async def test_pubsub_invalid_envelope_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.include_router(create_pubsub_router(_dispatcher(), allow_unverified=True))
    sentinel = "SECRET-PUBSUB-ENV-9911"
    body = json.dumps(
        {"message": {"data": f"not base64 !!! {sentinel}", "messageId": "m1"}}
    ).encode()
    result = await _post(app, "/pubsub", body, {"content-type": "application/json"})
    assert result.status_code == 400
    assert sentinel not in result.text
    assert sentinel not in _sentinel_logs(caplog)


async def test_workspace_non_json_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(_events_dispatcher(), allow_unverified=True)
    )
    sentinel = "SECRET-WS-JSON-9911"
    result = await _post(
        app,
        "/workspace-events",
        f"not json {sentinel}".encode(),
        {"content-type": "text/plain"},
    )
    assert result.status_code == 400
    assert sentinel not in result.text
    assert sentinel not in _sentinel_logs(caplog)


async def test_workspace_invalid_envelope_redacted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = FastAPI()
    app.include_router(
        create_workspace_events_router(_events_dispatcher(), allow_unverified=True)
    )
    sentinel = "SECRET-WS-ENV-9911"
    body = json.dumps(
        {
            "message": {
                "data": f"invalid {sentinel}",  # not base64
                "messageId": "m1",
                "attributes": {},  # no ce-* context attributes
            }
        }
    ).encode()
    result = await _post(
        app, "/workspace-events", body, {"content-type": "application/json"}
    )
    assert result.status_code == 400
    assert sentinel not in result.text
    assert sentinel not in _sentinel_logs(caplog)
