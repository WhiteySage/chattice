"""Immutable domain event tests."""

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from chattice.events import ActionEvent, Event, MessageEvent, UnknownEvent


def test_event_subclasses_and_defaults() -> None:
    message = MessageEvent(text="hello")
    action = ActionEvent(name="deploy")
    unknown = UnknownEvent(original_type="FUTURE")

    assert isinstance(message, Event)
    assert (message.event_type, action.event_type, unknown.event_type) == (
        "message",
        "action",
        "unknown",
    )


def test_events_are_frozen_and_slotted() -> None:
    event = MessageEvent(text="hello")

    with pytest.raises(FrozenInstanceError):
        cast(Any, event).text = "changed"
    with pytest.raises((AttributeError, TypeError)):
        cast(Any, event).new_field = True


def test_action_parameters_are_an_immutable_snapshot() -> None:
    source: dict[str, object] = {"environment": "prod"}
    event = ActionEvent(name="deploy", parameters=source)
    source["environment"] = "dev"

    assert event.parameters["environment"] == "prod"
    with pytest.raises(TypeError):
        cast(Any, event.parameters)["environment"] = "stage"


def test_raw_escape_hatch_preserves_identity_and_is_not_compared() -> None:
    raw: dict[str, object] = {"future": True}

    assert MessageEvent(text="x", raw=raw).raw is raw
    assert MessageEvent(text="x", raw=raw) == MessageEvent(text="x", raw=None)


def test_unknown_event_preserves_original_type_and_raw() -> None:
    raw = {"type": "SOME_FUTURE_EVENT"}
    event = UnknownEvent(original_type="SOME_FUTURE_EVENT", raw=raw)

    assert event.original_type == "SOME_FUTURE_EVENT"
    assert event.raw is raw
