"""Documented Cards v2 JSON <-> SDK proto helpers."""

from __future__ import annotations

import json
from typing import Any

from google.apps.card_v1.types.card import Card
from google.protobuf import json_format  # type: ignore[import-untyped]

__all__ = ["from_dict", "to_dict"]


def to_dict(card: Card) -> dict[str, Any]:
    """Serialize a Card proto into the documented camelCase Cards v2 JSON."""
    return json.loads(json_format.MessageToJson(card._pb))  # type: ignore[no-any-return]


def from_dict(data: dict[str, Any], *, ignore_unknown_fields: bool = False) -> Card:
    """Parse documented Cards v2 JSON back into a Card proto."""
    pb = json_format.Parse(
        json.dumps(data),
        Card.pb()(),
        ignore_unknown_fields=ignore_unknown_fields,
    )
    return Card(pb)
