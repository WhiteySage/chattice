"""Action and OpenLink facade builders."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from google.apps.card_v1.types.card import Action as ProtoAction
from google.apps.card_v1.types.card import OpenLink as ProtoOpenLink

__all__ = ["Action", "OpenLink"]


@dataclass(frozen=True, slots=True)
class Action:
    """An action invoked by a card widget (button click, form submit...)."""

    function: str | None = None
    parameters: Mapping[str, str] = field(default_factory=dict)
    # Documented wire value, e.g. ButtonInteraction.OPEN_DIALOG ("OPEN_DIALOG").
    interaction: str | None = None

    def to_proto(self) -> ProtoAction:
        """Build the SDK Action proto (parameters stay strings)."""
        kwargs: dict[str, Any] = {}
        if self.function is not None:
            kwargs["function"] = self.function
        kwargs["parameters"] = [
            {"key": key, "value": value} for key, value in self.parameters.items()
        ]
        if self.interaction is not None:
            kwargs["interaction"] = self.interaction
        return ProtoAction(**kwargs)

    @classmethod
    def from_proto(cls, proto: ProtoAction) -> Action:
        """Rebuild the facade from an SDK proto."""
        # proto.interaction is an SDK enum member; normalize to the wire string
        # name so the facade field stays str | None (round-trip friendly).
        # The zero value INTERACTION_UNSPECIFIED is falsy, so "if proto.interaction"
        # correctly yields None when unset.
        return cls(
            function=proto.function or None,
            parameters={p.key: p.value for p in proto.parameters},
            interaction=proto.interaction.name if proto.interaction else None,
        )


@dataclass(frozen=True, slots=True)
class OpenLink:
    """Opens a URL in a browser."""

    url: str
    open_as: Any = None

    def to_proto(self) -> ProtoOpenLink:
        """Build the SDK OpenLink proto."""
        kwargs: dict[str, Any] = {"url": self.url}
        if self.open_as is not None:
            kwargs["open_as"] = self.open_as
        return ProtoOpenLink(**kwargs)

    @classmethod
    def from_proto(cls, proto: ProtoOpenLink) -> OpenLink:
        """Rebuild the facade from an SDK proto."""
        return cls(url=proto.url, open_as=proto.open_as or None)
