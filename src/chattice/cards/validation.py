"""Form input validation facade."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from google.apps.card_v1.types.card import Validation as ProtoValidation
from google.protobuf import json_format  # type: ignore[import-untyped]

__all__ = ["TextInputType", "Validation"]


class TextInputType(Enum):
    """Documented Validation inputType values (SDK enum mirror)."""

    TEXT = "TEXT"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    EMAIL = "EMAIL"
    EMOJI_PICKER = "EMOJI_PICKER"

    def to_proto(self) -> Any:
        """Map to the SDK Validation.InputType enum member."""
        return getattr(ProtoValidation.InputType, self.value)


@dataclass(frozen=True, slots=True)
class Validation:
    """Validation rules for a form input."""

    character_limit: int | None = None
    input_type: TextInputType | None = None

    def to_proto(self) -> ProtoValidation:
        """Build the SDK Validation proto."""
        kwargs: dict[str, Any] = {}
        if self.character_limit is not None:
            kwargs["character_limit"] = self.character_limit
        if self.input_type is not None:
            kwargs["input_type"] = self.input_type.to_proto()
        return ProtoValidation(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the documented camelCase JSON."""
        return json.loads(json_format.MessageToJson(self.to_proto()._pb))  # type: ignore[no-any-return]
