"""Dynamic widget interaction event."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .base import Event
from .form import FormInputs


@dataclass(frozen=True, slots=True, kw_only=True)
class WidgetUpdatedEvent(Event):
    """A widget with an associated action was updated."""

    event_type: str = field(default="widget_updated", init=False)
    function_name: str = ""
    parameters: Mapping[str, str] = field(default_factory=dict)
    form_inputs: FormInputs = field(default_factory=FormInputs)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


__all__ = ["WidgetUpdatedEvent"]
