"""Typed per-call request configuration for outbound operations.

The retry and metadata fields reuse GAPIC types directly — no parallel
abstraction over what the SDK already defines.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from google.api_core.retry import AsyncRetry

__all__ = ["RequestConfig"]

_Metadata = Sequence[tuple[str, str | bytes]]


@dataclass(frozen=True, slots=True)
class RequestConfig:
    """Immutable, shared-safe per-call GAPIC request configuration.

    ``None`` / empty values mean "GAPIC default" — the executor passes
    them through unchanged, preserving raw GAPIC behavior.
    """

    timeout: float | None = None
    retry: AsyncRetry | None = None
    metadata: _Metadata = field(default_factory=tuple)
