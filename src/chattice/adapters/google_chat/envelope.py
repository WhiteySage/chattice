"""Normalization of documented Google Chat HTTP envelope families."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from .exceptions import (
    ConflictingEnvelopeError,
    InvalidInteractionPayload,
    UnsupportedEnvelopeError,
)


@dataclass(frozen=True, slots=True)
class NormalizedEnvelope:
    event: dict[str, object]
    raw: dict[str, object]


def normalize_envelope(payload: Mapping[str, object]) -> NormalizedEnvelope:
    """Deep-snapshot and normalize direct or App Home-style interaction JSON."""
    if not isinstance(payload, Mapping):
        raise InvalidInteractionPayload("Interaction payload must be a mapping")
    if any(not isinstance(key, str) for key in payload):
        raise InvalidInteractionPayload("Interaction payload keys must be strings")

    raw = deepcopy(dict(payload))
    direct_type = raw.get("type")
    wrapped = raw.get("chat")

    if wrapped is None:
        if direct_type is None:
            raise UnsupportedEnvelopeError(
                "Expected a direct 'type' field or wrapped 'chat' event"
            )
        event = dict(raw)
        event.pop("commonEventObject", None)
    else:
        if not isinstance(wrapped, Mapping):
            raise UnsupportedEnvelopeError("The wrapped 'chat' value must be a mapping")
        wrapped_event = dict(wrapped)
        wrapped_type = wrapped_event.get("type")
        if wrapped_type is None:
            raise UnsupportedEnvelopeError("The wrapped 'chat' event requires 'type'")
        event = wrapped_event
        if direct_type is not None:
            if direct_type != wrapped_type:
                raise ConflictingEnvelopeError(
                    "Direct and wrapped event types conflict: "
                    f"{direct_type!r} != {wrapped_type!r}"
                )
            for key, value in raw.items():
                if key in {"chat", "commonEventObject", "common", "type"}:
                    continue
                if key in event and event[key] != value:
                    raise ConflictingEnvelopeError(
                        f"Direct and wrapped event field {key!r} conflicts"
                    )
                event.setdefault(key, value)

    inner_common = event.get("common")
    outer_common = raw.get("commonEventObject")
    if inner_common is not None and not isinstance(inner_common, Mapping):
        raise InvalidInteractionPayload("'common' must be a mapping")
    if outer_common is not None and not isinstance(outer_common, Mapping):
        raise InvalidInteractionPayload("'commonEventObject' must be a mapping")
    if inner_common is not None and outer_common is not None:
        if dict(inner_common) != dict(outer_common):
            raise ConflictingEnvelopeError(
                "'common' and 'commonEventObject' contain conflicting data"
            )
    if outer_common is not None:
        event["common"] = dict(outer_common)

    return NormalizedEnvelope(event=event, raw=raw)


__all__ = ["NormalizedEnvelope", "normalize_envelope"]
