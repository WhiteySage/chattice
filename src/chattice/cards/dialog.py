"""Dialog facade (chat SDK Dialog proto)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from google.apps.chat_v1.types import Dialog as ProtoDialog
from google.protobuf import json_format  # type: ignore[import-untyped]

from .card import Card
from .raw import RawWidget
from .widgets import DateTimePicker

__all__ = ["Dialog"]


def _reject_datetime_picker(widget: object) -> None:
    # Documented Google rule: DateTimePicker is unsupported in dialogs,
    # enforced on the SERIALIZED widget tree, so the same constraint
    # holds for typed widgets AND raw-widget escape hatches (a
    # dateTimePicker smuggled through a RawWidget used to bypass it).
    if isinstance(widget, DateTimePicker) or (
        isinstance(widget, RawWidget) and "dateTimePicker" in widget.to_dict()
    ):
        raise ValueError(
            "DateTimePicker is not supported inside dialogs (documented "
            "Google Chat constraint); use it in card messages instead"
        )


@dataclass(frozen=True, slots=True)
class Dialog:
    """A dialog body displayed to the user who triggered the interaction."""

    body: Card

    def __post_init__(self) -> None:
        for section in self.body.sections:
            for widget in section.widgets:
                _reject_datetime_picker(widget)

    def to_proto(self) -> ProtoDialog:
        """Build the chat SDK Dialog proto."""
        return ProtoDialog(body=self.body.to_proto())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON shape carried under dialogAction.dialog.

        The Chat REST API nests the dialog under ``dialogAction.dialog``,
        so the payload is returned as ``{"dialog": {"body": ...}}``.
        """
        return {"dialog": json.loads(json_format.MessageToJson(self.to_proto()._pb))}
