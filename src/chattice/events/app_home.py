"""App Home interaction events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .base import Event
from .form import FormInputs


@dataclass(frozen=True, slots=True, kw_only=True)
class AppHomeEvent(Event):
    """A user opened the Chat app's Home tab."""

    event_type: str = field(default="app_home", init=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class FormSubmitEvent(Event):
    """A form submitted from App Home."""

    event_type: str = field(default="form_submit", init=False)
    function_name: str = ""
    parameters: Mapping[str, str] = field(default_factory=dict)
    form_inputs: FormInputs = field(default_factory=FormInputs)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


__all__ = ["AppHomeEvent", "FormSubmitEvent"]
