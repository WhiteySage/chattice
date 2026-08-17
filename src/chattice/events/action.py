"""Action domain event."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from .base import Event
from .form import FormInputs
from .references import MessageRef


class ActionSource(StrEnum):
    """The Google Chat surface that produced a card action."""

    MESSAGE = "MESSAGE"
    DIALOG = "DIALOG"
    HOME = "HOME"


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionEvent(Event):
    """A named action with immutable application parameters."""

    event_type: str = field(default="action", init=False)
    name: str = ""
    parameters: Mapping[str, object] = field(default_factory=dict)
    form_inputs: FormInputs = field(default_factory=FormInputs)
    sender_type: str | None = None
    source: ActionSource | None = None
    # Message identity of the clicked card — HTTP responses do not need it
    # (Google knows the target), Pub/Sub answers need it for
    # Bot.update_message. Live-verified during development.
    message: MessageRef | None = None

    def __post_init__(self) -> None:
        """Take a shallow immutable snapshot of action parameters."""
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))

    @property
    def function_name(self) -> str:
        """Google's normalized invoked function while retaining Phase 1 ``name``."""
        return self.name


__all__ = ["ActionEvent", "ActionSource"]
