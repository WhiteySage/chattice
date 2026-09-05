"""Filter contracts and evaluation helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from typing import Protocol, TypeAlias

from chattice.events import Event
from chattice.exceptions import ContextConflictError, FilterError

FilterValue: TypeAlias = bool | Mapping[str, object]
FilterCallable: TypeAlias = Callable[
    [Event, Mapping[str, object]], Awaitable[FilterValue]
]


class Filter(Protocol):
    """Structural protocol implemented by asynchronous custom filters."""

    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue: ...


class BaseFilter:
    """Convenience base class for asynchronous custom filters."""

    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        raise NotImplementedError


FilterLike: TypeAlias = BaseFilter | FilterCallable


async def evaluate_filters(
    filters: tuple[FilterLike, ...],
    event: Event,
    data: MutableMapping[str, object],
) -> bool:
    """Evaluate filters in order and merge dependency mappings safely."""
    for filter_ in filters:
        result = await filter_(event, data)
        if isinstance(result, bool):
            if not result:
                return False
            continue
        if not isinstance(result, Mapping):
            raise FilterError(
                f"Filter {filter_!r} returned {type(result).__name__}; "
                "expected bool or mapping"
            )
        for key, value in result.items():
            if not isinstance(key, str):
                raise FilterError("Filter context keys must be strings")
            if key in data:
                raise ContextConflictError(
                    f"Filter {filter_!r} attempted to redefine context key {key!r}"
                )
            data[key] = value
    return True


__all__ = ["BaseFilter", "Filter", "FilterLike", "FilterValue"]
