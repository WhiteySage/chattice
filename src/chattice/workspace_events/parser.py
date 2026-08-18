"""CloudEvent envelope parsing for Workspace Events."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import cast

from chattice._json_snapshot import deep_snapshot

from .envelope import (
    REQUIRED_SPECVERSION,
    TYPE_PREFIX,
    WorkspaceEventError,
    parse_event_time,
)

_REQUIRED_CE_ATTRIBUTES = ("ce-id", "ce-source", "ce-specversion", "ce-type")


class WorkspaceEventType:
    """Documented Chat Workspace event type strings (forward-compatible).

    Sources: https://developers.google.com/workspace/events/guides/events-chat
    and https://developers.google.com/workspace/events/guides/events-lifecycle
    (verified 2026-08-18, including batch event types).
    """

    MESSAGE_CREATED = "google.workspace.chat.message.v1.created"
    MESSAGE_UPDATED = "google.workspace.chat.message.v1.updated"
    MESSAGE_DELETED = "google.workspace.chat.message.v1.deleted"
    REACTION_CREATED = "google.workspace.chat.reaction.v1.created"
    REACTION_DELETED = "google.workspace.chat.reaction.v1.deleted"
    MEMBERSHIP_CREATED = "google.workspace.chat.membership.v1.created"
    MEMBERSHIP_UPDATED = "google.workspace.chat.membership.v1.updated"
    MEMBERSHIP_DELETED = "google.workspace.chat.membership.v1.deleted"
    SPACE_UPDATED = "google.workspace.chat.space.v1.updated"
    SPACE_DELETED = "google.workspace.chat.space.v1.deleted"
    SPACE_READ_STATE_UPDATED = "google.workspace.chat.spaceReadState.v1.updated"
    THREAD_READ_STATE_UPDATED = "google.workspace.chat.threadReadState.v1.updated"
    AVAILABILITY_UPDATED = "google.workspace.chat.availability.v1.updated"
    # Batch event types (output only): delivered automatically for any
    # subscribed type, never specified when creating a subscription.
    # No space.v1.batchDeleted / batch availability / batch read-state
    # creation-deletion types are documented.
    MESSAGE_BATCH_CREATED = "google.workspace.chat.message.v1.batchCreated"
    MESSAGE_BATCH_UPDATED = "google.workspace.chat.message.v1.batchUpdated"
    MESSAGE_BATCH_DELETED = "google.workspace.chat.message.v1.batchDeleted"
    REACTION_BATCH_CREATED = "google.workspace.chat.reaction.v1.batchCreated"
    REACTION_BATCH_DELETED = "google.workspace.chat.reaction.v1.batchDeleted"
    MEMBERSHIP_BATCH_CREATED = "google.workspace.chat.membership.v1.batchCreated"
    MEMBERSHIP_BATCH_UPDATED = "google.workspace.chat.membership.v1.batchUpdated"
    MEMBERSHIP_BATCH_DELETED = "google.workspace.chat.membership.v1.batchDeleted"
    SPACE_BATCH_UPDATED = "google.workspace.chat.space.v1.batchUpdated"
    SPACE_READ_STATE_BATCH_UPDATED = (
        "google.workspace.chat.spaceReadState.v1.batchUpdated"
    )
    THREAD_READ_STATE_BATCH_UPDATED = (
        "google.workspace.chat.threadReadState.v1.batchUpdated"
    )
    SUBSCRIPTION_SUSPENDED = "google.workspace.events.subscription.v1.suspended"
    SUBSCRIPTION_EXPIRATION_REMINDER = (
        "google.workspace.events.subscription.v1.expirationReminder"
    )
    SUBSCRIPTION_EXPIRED = "google.workspace.events.subscription.v1.expired"


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceEvent:
    """A Workspace resource-change event (NOT a Chat interaction)."""

    event_type: str = field(default="workspace_event", init=False)
    event_id: str
    source: str
    subject: str | None = None
    event_time: datetime | None = None
    data: Mapping[str, object] = field(default_factory=dict)
    cloud_type: str = ""
    raw: Mapping[str, object] = field(default_factory=dict)


def parse_workspace_event(payload: Mapping[str, object]) -> WorkspaceEvent:
    """Parse a CloudEvents 1.0 Workspace event into a WorkspaceEvent.

    Accepts a STRUCTURED CloudEvent (all fields at the top level). This form
    is for offline use (fixtures, replays, tests) — Google delivers Workspace
    Events exclusively through Pub/Sub push messages; see
    :func:`parse_workspace_envelope` for the wire format.
    """
    if not isinstance(payload, Mapping):
        raise WorkspaceEventError("Workspace event payload must be a mapping")
    if payload.get("specversion") != REQUIRED_SPECVERSION:
        raise WorkspaceEventError(
            f"Unsupported specversion {payload.get('specversion')!r}; "
            f"expected {REQUIRED_SPECVERSION!r}"
        )
    event_id = payload.get("id")
    if not isinstance(event_id, str):
        raise WorkspaceEventError("Workspace event 'id' must be a string")
    source = payload.get("source")
    if not isinstance(source, str):
        raise WorkspaceEventError("Workspace event 'source' must be a string")
    cloud_type = payload.get("type")
    if not isinstance(cloud_type, str) or not cloud_type.startswith(TYPE_PREFIX):
        raise WorkspaceEventError(
            f"Workspace event 'type' must be a {TYPE_PREFIX!r}-prefixed string"
        )
    subject = payload.get("subject")
    if subject is not None and not isinstance(subject, str):
        raise WorkspaceEventError(
            "Workspace event 'subject' must be a string or absent"
        )
    event_time = parse_event_time(payload.get("time"))
    data = payload.get("data")
    if data is None:
        data = {}
    if not isinstance(data, Mapping):
        raise WorkspaceEventError("Workspace event 'data' must be a mapping or absent")
    # deep snapshots — mutating the caller's nested values (e.g.
    # data.message.text) after parsing must not change the parsed event.
    return WorkspaceEvent(
        event_id=event_id,
        source=source,
        subject=subject,
        event_time=event_time,
        data=cast(
            Mapping[str, object],
            MappingProxyType(
                cast(
                    dict[str, object], deep_snapshot(data, where="WorkspaceEvent.data")
                )
            ),
        ),
        cloud_type=cloud_type,
        raw=cast(
            Mapping[str, object],
            MappingProxyType(
                cast(
                    dict[str, object],
                    deep_snapshot(payload, where="WorkspaceEvent.raw"),
                )
            ),
        ),
    )


def parse_workspace_envelope(payload: Mapping[str, object]) -> WorkspaceEvent:
    """Parse an official Pub/Sub push envelope for Workspace Events.

    Google's binding (https://developers.google.com/workspace/events):
    the CloudEvents context attributes travel in ``message.attributes``
    (``ce-id``, ``ce-source``, ``ce-specversion``, ``ce-time``,
    ``ce-type``, optional ``ce-subject``/``ce-datacontenttype``), while
    base64-decoded ``message.data`` contains ONLY the event resource data
    (or resource names for names-only payloads). The full envelope is
    preserved in ``.raw``.
    """
    if not isinstance(payload, Mapping):
        raise WorkspaceEventError("Workspace event payload must be a mapping")
    message = payload.get("message")
    if message is None or not isinstance(message, Mapping):
        raise WorkspaceEventError(
            "Workspace push payload must be a Pub/Sub envelope with a 'message' object"
        )
    attributes = message.get("attributes")
    if attributes is None or not isinstance(attributes, Mapping):
        raise WorkspaceEventError(
            "Workspace push envelope requires 'message.attributes' (ce-* fields)"
        )
    for required in _REQUIRED_CE_ATTRIBUTES:
        value = attributes.get(required)
        if not isinstance(value, str) or not value:
            raise WorkspaceEventError(
                f"Workspace push envelope requires attribute {required!r}"
            )
    specversion = attributes["ce-specversion"]
    if specversion != REQUIRED_SPECVERSION:
        raise WorkspaceEventError(
            f"Unsupported specversion {specversion!r}; "
            f"expected {REQUIRED_SPECVERSION!r}"
        )
    cloud_type = attributes["ce-type"]
    if not cloud_type.startswith(TYPE_PREFIX):
        raise WorkspaceEventError(
            f"Workspace event 'type' must be a {TYPE_PREFIX!r}-prefixed string"
        )
    datacontenttype = attributes.get("ce-datacontenttype")
    if datacontenttype is not None and datacontenttype != "application/json":
        raise WorkspaceEventError(
            f"Unsupported ce-datacontenttype {datacontenttype!r}; "
            "expected 'application/json'"
        )
    subject = attributes.get("ce-subject")
    if subject is not None and not isinstance(subject, str):
        raise WorkspaceEventError(
            "Workspace event 'ce-subject' must be a string or absent"
        )
    event_time = parse_event_time(attributes.get("ce-time"))
    data = _decode_envelope_data(message)
    return WorkspaceEvent(
        event_id=attributes["ce-id"],
        source=attributes["ce-source"],
        subject=subject,
        event_time=event_time,
        data=MappingProxyType(dict(data)),
        cloud_type=cloud_type,
        raw=MappingProxyType(dict(payload)),
    )


def _decode_envelope_data(message: Mapping[str, object]) -> Mapping[str, object]:
    raw = message.get("data")
    if not isinstance(raw, str):
        raise WorkspaceEventError(
            "Workspace push envelope 'message.data' must be a base64 string"
        )
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as error:
        raise WorkspaceEventError(
            "Workspace push envelope 'message.data' is not valid base64"
        ) from error
    try:
        inner = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise WorkspaceEventError(
            "Workspace push envelope 'message.data' does not contain valid JSON"
        ) from error
    if not isinstance(inner, Mapping):
        raise WorkspaceEventError(
            "Workspace push envelope 'message.data' must decode to a JSON mapping"
        )
    return inner


__all__ = [
    "WorkspaceEvent",
    "WorkspaceEventType",
    "parse_workspace_envelope",
    "parse_workspace_event",
]
