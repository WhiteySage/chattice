"""Normalization of Google CommonEventObject form inputs."""

from __future__ import annotations

from collections.abc import Mapping

from chattice.events import (
    DateInput,
    DateTimeInput,
    FormInputs,
    FormValue,
    StringInput,
    TimeInput,
    UnknownFormInput,
)

from .exceptions import InvalidInteractionPayload

_KNOWN_INPUTS = {"stringInputs", "dateInput", "dateTimeInput", "timeInput"}


def parse_form_inputs(values: Mapping[str, object]) -> FormInputs:
    """Convert one-of input mappings without flattening widget semantics."""
    parsed: dict[str, FormValue] = {}
    for widget, input_value in values.items():
        if not isinstance(widget, str) or not isinstance(input_value, Mapping):
            raise InvalidInteractionPayload(
                "Every form input must have a string name and mapping value"
            )
        present = _KNOWN_INPUTS.intersection(input_value)
        if len(present) > 1:
            raise InvalidInteractionPayload(
                f"Form input {widget!r} contains multiple input variants"
            )
        if not present:
            kind = next(iter(input_value), "unknown")
            parsed[widget] = UnknownFormInput(kind=kind, raw=dict(input_value))
            continue
        kind = present.pop()
        body = input_value[kind]
        if not isinstance(body, Mapping):
            raise InvalidInteractionPayload(
                f"Form input {widget!r}.{kind} must be a mapping"
            )
        parsed[widget] = _parse_value(widget, kind, body)
    return FormInputs(data=parsed)


def _parse_value(widget: str, kind: str, body: Mapping[str, object]) -> FormValue:
    if kind == "stringInputs":
        value = body.get("value")
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            raise InvalidInteractionPayload(
                f"Form input {widget!r}.stringInputs.value must be a string list"
            )
        return StringInput(values=tuple(value))
    if kind == "dateInput":
        return DateInput(ms_since_epoch=_epoch(widget, body))
    if kind == "dateTimeInput":
        has_date = _optional_bool(widget, body, "hasDate")
        has_time = _optional_bool(widget, body, "hasTime")
        return DateTimeInput(
            ms_since_epoch=_epoch(widget, body),
            has_date=has_date,
            has_time=has_time,
        )
    hours = body.get("hours")
    minutes = body.get("minutes")
    if (
        not isinstance(hours, int)
        or isinstance(hours, bool)
        or not 0 <= hours <= 23
        or not isinstance(minutes, int)
        or isinstance(minutes, bool)
        or not 0 <= minutes <= 59
    ):
        raise InvalidInteractionPayload(
            f"Form input {widget!r}.timeInput requires valid hours/minutes"
        )
    return TimeInput(hours=hours, minutes=minutes)


def _epoch(widget: str, body: Mapping[str, object]) -> int:
    value = body.get("msSinceEpoch")
    if isinstance(value, bool):
        value = None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise InvalidInteractionPayload(
        f"Form input {widget!r} requires integer-compatible msSinceEpoch"
    )


def _optional_bool(widget: str, body: Mapping[str, object], key: str) -> bool | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise InvalidInteractionPayload(f"Form input {widget!r}.{key} must be boolean")
    return value


__all__ = ["parse_form_inputs"]
