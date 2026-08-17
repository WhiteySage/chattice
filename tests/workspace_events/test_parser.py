"""Workspace Events CloudEvent parsing."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping

import pytest

from chattice.workspace_events import (
    WorkspaceEvent,
    WorkspaceEventError,
    WorkspaceEventType,
    parse_workspace_envelope,
    parse_workspace_event,
)


def _cloudevent(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "specversion": "1.0",
        "id": "evt-1",
        "source": "//chat.googleapis.com/spaces/AAA",
        "type": "google.workspace.chat.message.v1.created",
        "time": "2026-08-15T10:00:00.123Z",
        "datacontenttype": "application/json",
        "data": {"message": {"name": "spaces/AAA/messages/1"}},
    }
    payload.update(overrides)
    return payload


def _envelope(
    *,
    attributes: dict[str, str] | None = None,
    data: object = {"message": {"name": "spaces/AAA/messages/1"}},
    data_raw: str | None = None,
) -> dict[str, object]:
    """The OFFICIAL Workspace Events Pub/Sub binding.

    CloudEvents context attributes travel in ``message.attributes``
    (``ce-*`` keys); base64-decoded ``message.data`` holds ONLY the event
    resource data.
    https://developers.google.com/workspace/events#events-as-google-cloud-pubsub-messages
    """
    if attributes is None:
        attributes = {
            "ce-id": "evt-1",
            "ce-source": "//chat.googleapis.com/spaces/AAA",
            "ce-specversion": "1.0",
            "ce-time": "2026-08-15T10:00:00.123Z",
            "ce-type": "google.workspace.chat.message.v1.created",
            "ce-subject": "spaces/AAA/messages/1",
        }
    if data_raw is None:
        data_raw = base64.b64encode(json.dumps(data).encode()).decode()
    return {
        "message": {
            "data": data_raw,
            "messageId": "m-1",
            "attributes": attributes,
        },
        "subscription": "projects/p/subscriptions/s",
    }


def test_valid_cloudevent() -> None:
    event = parse_workspace_event(_cloudevent())
    assert isinstance(event, WorkspaceEvent)
    assert event.event_id == "evt-1"
    assert event.cloud_type == WorkspaceEventType.MESSAGE_CREATED
    assert event.event_time is not None
    assert event.event_time.tzinfo is not None
    assert event.data["message"] == {"name": "spaces/AAA/messages/1"}


def test_missing_specversion() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(specversion=None))


def test_wrong_specversion() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(specversion="0.3"))


def test_non_string_type() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(type=123))


def test_type_without_prefix() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(type="chat.message.created"))


def test_non_mapping_data() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(data=[1, 2]))


def test_absent_data_is_empty() -> None:
    event = parse_workspace_event(_cloudevent(data=None))
    assert event.data == {}


def test_future_type_parses_forward_compatibly() -> None:
    event = parse_workspace_event(
        _cloudevent(type="google.workspace.chat.reaction.v1.created")
    )
    assert event.cloud_type == "google.workspace.chat.reaction.v1.created"


def test_naive_time_is_rejected() -> None:
    with pytest.raises(WorkspaceEventError):
        parse_workspace_event(_cloudevent(time="2026-08-15T10:00:00"))


def test_type_constants() -> None:
    assert (
        WorkspaceEventType.MESSAGE_CREATED == "google.workspace.chat.message.v1.created"
    )
    assert WorkspaceEventType.SPACE_UPDATED == "google.workspace.chat.space.v1.updated"


# --- Official Pub/Sub binding (parse_workspace_envelope) ---


def test_valid_pubsub_envelope() -> None:
    event = parse_workspace_envelope(_envelope())
    assert isinstance(event, WorkspaceEvent)
    assert event.event_id == "evt-1"
    assert event.source == "//chat.googleapis.com/spaces/AAA"
    assert event.cloud_type == WorkspaceEventType.MESSAGE_CREATED
    assert event.subject == "spaces/AAA/messages/1"
    assert event.event_time is not None and event.event_time.tzinfo is not None
    assert event.data["message"] == {"name": "spaces/AAA/messages/1"}


def test_envelope_names_only_data() -> None:
    """payloadOptions names-only: data carries resource names only."""
    event = parse_workspace_envelope(
        _envelope(data={"membership": {"name": "spaces/A/members/1"}})
    )
    assert event.data["membership"] == {"name": "spaces/A/members/1"}


def test_envelope_batch_type() -> None:
    event = parse_workspace_envelope(
        _envelope(
            attributes={
                "ce-id": "evt-b",
                "ce-source": "//chat.googleapis.com/spaces/AAA",
                "ce-specversion": "1.0",
                "ce-time": "2026-08-15T10:00:00Z",
                "ce-type": "google.workspace.chat.message.v1.batchCreated",
            }
        )
    )
    assert event.cloud_type == "google.workspace.chat.message.v1.batchCreated"


def test_envelope_lifecycle_type() -> None:
    event = parse_workspace_envelope(
        _envelope(
            attributes={
                "ce-id": "evt-l",
                "ce-source": "//workspaceevents.googleapis.com/subscriptions/SUB",
                "ce-specversion": "1.0",
                "ce-time": "2026-08-15T10:00:00Z",
                "ce-type": "google.workspace.events.subscription.v1.expired",
            },
            data={"subscription": {"name": "subscriptions/SUB"}},
        )
    )
    assert event.cloud_type == "google.workspace.events.subscription.v1.expired"
    assert event.data["subscription"] == {"name": "subscriptions/SUB"}


def test_envelope_forward_compatible_type() -> None:
    """Any google.workspace.* type is accepted (additive Google updates)."""
    event = parse_workspace_envelope(
        _envelope(
            attributes={
                "ce-id": "evt-a",
                "ce-source": "//chat.googleapis.com/spaces/AAA",
                "ce-specversion": "1.0",
                "ce-time": "2026-08-15T10:00:00Z",
                "ce-type": "google.workspace.chat.availability.v1.updated",
            }
        )
    )
    assert event.cloud_type == "google.workspace.chat.availability.v1.updated"


def test_envelope_raw_preserved() -> None:
    payload = _envelope()
    event = parse_workspace_envelope(payload)
    assert event.raw == payload
    raw = event.raw
    assert isinstance(raw, Mapping)
    assert raw["message"]["attributes"]["ce-id"] == "evt-1"


def test_envelope_optional_subject_and_time() -> None:
    attributes = {
        "ce-id": "evt-min",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "1.0",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    event = parse_workspace_envelope(_envelope(attributes=attributes))
    assert event.subject is None
    assert event.event_time is None


def test_envelope_requires_message() -> None:
    with pytest.raises(WorkspaceEventError, match="Pub/Sub"):
        parse_workspace_envelope({"subscription": "projects/p/subscriptions/s"})


def test_envelope_requires_attributes() -> None:
    with pytest.raises(WorkspaceEventError, match="attributes"):
        parse_workspace_envelope({"message": {"data": "e30=", "messageId": "m-1"}})


def test_envelope_requires_ce_id() -> None:
    attributes = {
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "1.0",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    with pytest.raises(WorkspaceEventError, match="ce-id"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_requires_ce_source() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-specversion": "1.0",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    with pytest.raises(WorkspaceEventError, match="ce-source"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_requires_ce_type() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "1.0",
    }
    with pytest.raises(WorkspaceEventError, match="ce-type"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_requires_specversion() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    with pytest.raises(WorkspaceEventError, match="ce-specversion"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_wrong_specversion() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "0.3",
        "ce-type": "google.workspace.chat.message.v1.created",
    }
    with pytest.raises(WorkspaceEventError, match="specversion"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_type_without_prefix() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "1.0",
        "ce-type": "chat.message.created",
    }
    with pytest.raises(WorkspaceEventError, match=r"google\.workspace"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_bad_base64() -> None:
    with pytest.raises(WorkspaceEventError, match="base64"):
        parse_workspace_envelope(_envelope(data_raw="not-base64!!"))


def test_envelope_non_json_data() -> None:
    raw = base64.b64encode(b"not json").decode()
    with pytest.raises(WorkspaceEventError, match="JSON"):
        parse_workspace_envelope(_envelope(data_raw=raw))


def test_envelope_non_mapping_data() -> None:
    raw = base64.b64encode(b"[1, 2]").decode()
    with pytest.raises(WorkspaceEventError, match="mapping"):
        parse_workspace_envelope(_envelope(data_raw=raw))


def test_envelope_non_json_datacontenttype() -> None:
    attributes = {
        "ce-id": "evt-1",
        "ce-source": "//chat.googleapis.com/spaces/AAA",
        "ce-specversion": "1.0",
        "ce-type": "google.workspace.chat.message.v1.created",
        "ce-datacontenttype": "text/plain",
    }
    with pytest.raises(WorkspaceEventError, match="datacontenttype"):
        parse_workspace_envelope(_envelope(attributes=attributes))


def test_envelope_type_constants_cover_official_set() -> None:
    """The constants cover the documented stable Chat event type strings."""
    expected = {
        WorkspaceEventType.MESSAGE_CREATED,
        WorkspaceEventType.MESSAGE_UPDATED,
        WorkspaceEventType.MESSAGE_DELETED,
        WorkspaceEventType.REACTION_CREATED,
        WorkspaceEventType.REACTION_DELETED,
        WorkspaceEventType.MEMBERSHIP_CREATED,
        WorkspaceEventType.MEMBERSHIP_UPDATED,
        WorkspaceEventType.MEMBERSHIP_DELETED,
        WorkspaceEventType.SPACE_UPDATED,
        WorkspaceEventType.SPACE_DELETED,
        WorkspaceEventType.SPACE_READ_STATE_UPDATED,
        WorkspaceEventType.THREAD_READ_STATE_UPDATED,
        WorkspaceEventType.AVAILABILITY_UPDATED,
        WorkspaceEventType.SUBSCRIPTION_SUSPENDED,
        WorkspaceEventType.SUBSCRIPTION_EXPIRATION_REMINDER,
        WorkspaceEventType.SUBSCRIPTION_EXPIRED,
    }
    for name, value in vars(WorkspaceEventType).items():
        if name.startswith("_"):
            continue
        assert isinstance(value, str)
        assert value.startswith("google.workspace.")
    assert all(
        value in {v for _, v in vars(WorkspaceEventType).items()} for value in expected
    )
