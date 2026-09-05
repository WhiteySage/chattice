"""Lossless raw escape hatches for the Cards facade (ADR-007 promise).

``RawWidget`` carries an arbitrary widget as its DOCUMENTED camelCase
JSON: future/niche widget kinds need no facade. The dict path
(``to_dict`` / card JSON) is lossless; the SDK proto path parses the
known fields and ignores unknown ones (protos cannot represent unknown
fields). The payload is validated against the Widget schema — invalid
known fields fail loudly at construction time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from google.apps.card_v1.types.card import Widget as ProtoWidget
from google.protobuf import json_format  # type: ignore[import-untyped]

from chattice._json_snapshot import deep_snapshot

__all__ = ["RawWidget"]


@dataclass(frozen=True, slots=True)
class RawWidget:
    """An arbitrary Cards v2 widget as documented camelCase JSON.

    The payload is deep-snapshotted at construction — mutating the
    caller's mapping (including nested values) afterwards cannot change
    the widget, and the snapshot is what ``to_dict`` returns.
    """

    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        snapshot = cast(
            dict[str, object],
            deep_snapshot(self.payload, where="RawWidget.payload"),
        )
        try:
            json_format.ParseDict(
                snapshot,
                ProtoWidget()._pb,
                ignore_unknown_fields=True,
            )
        except Exception as error:
            raise ValueError(
                f"RawWidget payload is not a valid Cards v2 widget: {error}"
            ) from error
        object.__setattr__(self, "payload", snapshot)

    def to_dict(self) -> dict[str, object]:
        """The documented camelCase widget JSON (lossless snapshot)."""
        return dict(self.payload)
