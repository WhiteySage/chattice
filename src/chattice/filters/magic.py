"""A small, safe expression-tree filtering DSL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias

from chattice.events import Event

from .base import BaseFilter, FilterValue


class _Missing:
    __slots__ = ()


MISSING: Final = _Missing()
PathStep: TypeAlias = tuple[Literal["attr", "item"], object]


class MagicExpression(BaseFilter):
    """Base class for immutable boolean expression nodes."""

    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        del context
        return self.evaluate(event)

    def evaluate(self, event: Event) -> bool:
        """Evaluate this expression against an event."""
        raise NotImplementedError

    def __and__(self, other: MagicExpression) -> MagicExpression:
        return _BooleanExpression("and", self, other)

    def __or__(self, other: MagicExpression) -> MagicExpression:
        return _BooleanExpression("or", self, other)

    def __invert__(self) -> MagicExpression:
        return _NotExpression(self)

    def __bool__(self) -> bool:
        raise TypeError("Magic-filter expressions cannot be used as Python booleans")


@dataclass(frozen=True, slots=True)
class MagicField(MagicExpression):
    """A safely traversed event attribute/item path."""

    path: tuple[PathStep, ...] = ()

    def __getattr__(self, name: str) -> MagicField:
        if name.startswith("__"):
            raise AttributeError(name)
        return MagicField((*self.path, ("attr", name)))

    def __getitem__(self, key: object) -> MagicField:
        return MagicField((*self.path, ("item", key)))

    def __eq__(self, other: object) -> MagicExpression:  # type: ignore[override]
        return _ComparisonExpression("eq", self, other)

    def __ne__(self, other: object) -> MagicExpression:  # type: ignore[override]
        return _ComparisonExpression("ne", self, other)

    def __lt__(self, other: object) -> MagicExpression:
        return _ComparisonExpression("lt", self, other)

    def __le__(self, other: object) -> MagicExpression:
        return _ComparisonExpression("le", self, other)

    def __gt__(self, other: object) -> MagicExpression:
        return _ComparisonExpression("gt", self, other)

    def __ge__(self, other: object) -> MagicExpression:
        return _ComparisonExpression("ge", self, other)

    def contains(self, value: object) -> MagicExpression:
        """Match when the resolved field contains ``value``."""
        return _MethodExpression("contains", self, value)

    def startswith(self, value: object) -> MagicExpression:
        """Match when the resolved field starts with ``value``."""
        return _MethodExpression("startswith", self, value)

    def endswith(self, value: object) -> MagicExpression:
        """Match when the resolved field ends with ``value``."""
        return _MethodExpression("endswith", self, value)

    def in_(self, value: object) -> MagicExpression:
        """Match when the resolved field is a member of ``value``."""
        return _MethodExpression("in", self, value)

    def is_(self, value: object) -> MagicExpression:
        """Match by object identity."""
        return _MethodExpression("is", self, value)

    def exists(self) -> MagicExpression:
        """Match when the complete path can be resolved."""
        return _MethodExpression("exists", self, None)

    def resolve(self, event: Event) -> object:
        """Resolve this path, returning an internal missing sentinel on absence."""
        current: object = event
        for operation, value in self.path:
            try:
                if operation == "attr":
                    current = getattr(current, str(value))
                else:
                    current = current[value]  # type: ignore[index]
            except (AttributeError, KeyError, IndexError, TypeError):
                return MISSING
        return current

    def evaluate(self, event: Event) -> bool:
        value = self.resolve(event)
        return value is not MISSING and bool(value)


@dataclass(frozen=True, slots=True)
class _ComparisonExpression(MagicExpression):
    operation: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    field: MagicField
    expected: object

    def evaluate(self, event: Event) -> bool:
        actual = self.field.resolve(event)
        if actual is MISSING:
            return False
        try:
            if self.operation == "eq":
                return bool(actual == self.expected)
            if self.operation == "ne":
                return bool(actual != self.expected)
            if self.operation == "lt":
                return bool(actual < self.expected)  # type: ignore[operator]
            if self.operation == "le":
                return bool(actual <= self.expected)  # type: ignore[operator]
            if self.operation == "gt":
                return bool(actual > self.expected)  # type: ignore[operator]
            return bool(actual >= self.expected)  # type: ignore[operator]
        except TypeError:
            return False


@dataclass(frozen=True, slots=True)
class _MethodExpression(MagicExpression):
    operation: Literal["contains", "startswith", "endswith", "in", "is", "exists"]
    field: MagicField
    expected: object

    def evaluate(self, event: Event) -> bool:
        actual = self.field.resolve(event)
        if self.operation == "exists":
            return actual is not MISSING
        if actual is MISSING:
            return False
        if self.operation == "is":
            return actual is self.expected
        try:
            if self.operation == "contains":
                return self.expected in actual  # type: ignore[operator]
            if self.operation == "in":
                return actual in self.expected  # type: ignore[operator]
            if self.operation == "startswith":
                return bool(actual.startswith(self.expected))  # type: ignore[attr-defined]
            return bool(actual.endswith(self.expected))  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            return False


@dataclass(frozen=True, slots=True)
class _BooleanExpression(MagicExpression):
    operation: Literal["and", "or"]
    left: MagicExpression
    right: MagicExpression

    def evaluate(self, event: Event) -> bool:
        if self.operation == "and":
            return self.left.evaluate(event) and self.right.evaluate(event)
        return self.left.evaluate(event) or self.right.evaluate(event)


@dataclass(frozen=True, slots=True)
class _NotExpression(MagicExpression):
    expression: MagicExpression

    def evaluate(self, event: Event) -> bool:
        return not self.expression.evaluate(event)


F: Final = MagicField()

__all__ = ["F", "MagicExpression", "MagicField"]
