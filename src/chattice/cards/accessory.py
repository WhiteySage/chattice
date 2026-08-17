"""Message accessory widgets (Google GA surface).

Documented constraints (verified 2026-08-15):
- ``buttonList`` is the only supported accessory kind;
- app authentication is required to CREATE messages with accessory
  widgets;
- accessory widgets are not supported on messages containing dialogs.

Clicks on accessory buttons arrive as the SAME ``CARD_CLICKED``
interactions as card buttons: they reuse ``ActionEvent`` and
``router.action(...)`` — no second callback subsystem.
"""

from __future__ import annotations

import json as jsonlib
from dataclasses import dataclass

from google.apps.chat_v1.types.message import AccessoryWidget as ProtoAccessoryWidget
from google.protobuf.json_format import MessageToJson  # type: ignore[import-untyped]

from .widgets import ButtonList

__all__ = ["AccessoryWidget"]


@dataclass(frozen=True, slots=True)
class AccessoryWidget:
    """A message accessory widget (button list)."""

    button_list: ButtonList

    def to_proto(self) -> ProtoAccessoryWidget:
        return ProtoAccessoryWidget(button_list=self.button_list.to_proto())

    def to_dict(self) -> dict[str, object]:
        """The documented camelCase JSON shape (message.accessoryWidgets entry)."""
        return jsonlib.loads(  # type: ignore[no-any-return]
            MessageToJson(self.to_proto()._pb)
        )
