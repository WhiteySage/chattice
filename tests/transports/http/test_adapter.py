"""Interaction context and HTTP adapter."""

from __future__ import annotations

import datetime
import json

import pytest

from chattice.adapters.google_chat.exceptions import InvalidInteractionPayload
from chattice.events import MessageEvent
from chattice.transports.http import (
    SYNC_RESPONSE_DEADLINE,
    HTTPInteractionAdapter,
    IncomingRequest,
    InteractionContext,
    InteractionResponse,
)


def _request(body: str) -> IncomingRequest:
    return IncomingRequest(method="POST", path="/", body=body.encode())


def test_deadline_is_documented_30_seconds() -> None:
    assert SYNC_RESPONSE_DEADLINE == datetime.timedelta(seconds=30)


def test_adapter_parses_documented_payload() -> None:
    payload = {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
    }
    event = HTTPInteractionAdapter().parse(_request(json.dumps(payload)))
    assert isinstance(event, MessageEvent)
    assert event.text == "ping"


def test_adapter_rejects_invalid_json() -> None:
    with pytest.raises(InvalidInteractionPayload):
        HTTPInteractionAdapter().parse(_request("{not json"))


def test_context_exposes_remaining_time() -> None:
    request = _request("{}")
    response = InteractionResponse()
    context = InteractionContext(
        request=request,
        response=response,
        received_at=request.received_at,
        deadline_at=request.received_at + SYNC_RESPONSE_DEADLINE,
    )
    assert datetime.timedelta(0) < context.remaining <= SYNC_RESPONSE_DEADLINE
    assert context.request is request
    assert context.response is response
