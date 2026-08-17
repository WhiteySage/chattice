"""Internal deep-snapshot utility for frozen boundaries.

Frozen facade objects must not retain caller-owned mutable graphs:
snapshots are rebuilt recursively into new JSON-like values. Shared by
the cards facades, event parsing and workspace events — one utility, one
contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

__all__ = ["deep_snapshot"]


def deep_snapshot(value: object, *, where: str) -> object:
    """Deep-copy a value into fresh JSON-like data (str/int/float/bool/
    None/dict/list). Enums reduce to their values; everything else is
    rejected — boundary objects must not carry provider or caller types.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return deep_snapshot(value.value, where=where)
    if isinstance(value, Mapping):
        return {
            str(key): deep_snapshot(item, where=where) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [deep_snapshot(item, where=where) for item in value]
    raise TypeError(
        f"{where} must be JSON-like (str/int/float/bool/None/list/dict); "
        f"got {type(value).__name__}"
    )
