"""Dialog action status facade."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionStatusCode(Enum):
    """Documented ActionStatus.StatusCode values."""

    OK = "OK"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"


@dataclass(frozen=True, slots=True)
class ActionStatus:
    """The outcome of a dialog submit, shown to the user."""

    status_code: ActionStatusCode
    user_facing_message: str | None = None

    @classmethod
    def ok(cls, message: str | None = None) -> ActionStatus:
        """A successful submit (optional success message)."""
        return cls(ActionStatusCode.OK, message)

    @classmethod
    def invalid(cls, message: str) -> ActionStatus:
        """A validation failure shown to the user."""
        return cls(ActionStatusCode.INVALID_ARGUMENT, message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the documented actionStatus JSON."""
        data: dict[str, Any] = {"statusCode": self.status_code.value}
        if self.user_facing_message is not None:
            data["userFacingMessage"] = self.user_facing_message
        return data


__all__ = ["ActionStatus", "ActionStatusCode"]
