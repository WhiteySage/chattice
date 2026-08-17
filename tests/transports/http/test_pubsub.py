"""Pub/Sub push envelope adapter."""

from __future__ import annotations

import base64
import json
from typing import cast

import pytest

from chattice.events import MessageEvent
from chattice.transports.pubsub import PubSubEnvelopeError, PubSubPushAdapter


def _envelope(
    payload: dict[str, object], **message_overrides: object
) -> dict[str, object]:
    raw = json.dumps(payload).encode()
    message: dict[str, object] = {
        "data": base64.b64encode(raw).decode(),
        "messageId": "m-1",
        "publishTime": "2026-08-15T10:00:00Z",
    }
    message.update(message_overrides)
    return {"message": message, "subscription": "projects/p/subscriptions/s"}


def _interaction() -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
    }


def test_valid_envelope() -> None:
    event = PubSubPushAdapter().parse_envelope(_envelope(_interaction()))
    assert isinstance(event, MessageEvent)
    assert event.text == "ping"
    raw = cast(dict[str, object], event.raw)
    assert raw["subscription"] == "projects/p/subscriptions/s"
    message = cast(dict[str, object], raw["message"])
    assert message["messageId"] == "m-1"


def test_bad_base64() -> None:
    with pytest.raises(PubSubEnvelopeError):
        PubSubPushAdapter().parse_envelope(
            _envelope(_interaction(), data="%%%not-base64")
        )


def test_bad_json_inside_data() -> None:
    bad = base64.b64encode(b"{not json").decode()
    with pytest.raises(PubSubEnvelopeError):
        PubSubPushAdapter().parse_envelope(_envelope(_interaction(), data=bad))


def test_missing_data() -> None:
    with pytest.raises(PubSubEnvelopeError):
        PubSubPushAdapter().parse_envelope(_envelope(_interaction(), data=None))


def test_non_mapping_envelope() -> None:
    with pytest.raises(PubSubEnvelopeError):
        PubSubPushAdapter().parse_envelope([1, 2])  # type: ignore[arg-type]
