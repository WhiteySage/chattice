"""Information-preserving form input domain values."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True, kw_only=True)
class StringInput:
    """One or more text or selection values."""

    values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class DateInput:
    """A date represented by Google's lossless epoch-millisecond value."""

    ms_since_epoch: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DateTimeInput:
    """A date/time input with the documented component-presence flags."""

    ms_since_epoch: int
    has_date: bool | None = None
    has_time: bool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeInput:
    """Wall-clock time components."""

    hours: int
    minutes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownFormInput:
    """A future input variant retained without claiming its semantics."""

    kind: str
    raw: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", MappingProxyType(dict(self.raw)))


FormValue = StringInput | DateInput | DateTimeInput | TimeInput | UnknownFormInput


@dataclass(frozen=True, slots=True, kw_only=True)
class FormInputs(Mapping[str, FormValue]):
    """Immutable mapping from widget names to typed submitted values."""

    data: Mapping[str, FormValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def __getitem__(self, key: str) -> FormValue:
        return self.data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)


__all__ = [
    "DateInput",
    "DateTimeInput",
    "FormInputs",
    "FormValue",
    "StringInput",
    "TimeInput",
    "UnknownFormInput",
]
