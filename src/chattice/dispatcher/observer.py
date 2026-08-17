"""Ordered event-observer registrations."""

from __future__ import annotations

from collections.abc import Callable

from chattice.filters import F, FilterLike

from .dependency import HandlerCallback
from .handler import HandlerObject


class EventObserver:
    """An ordered collection of handlers for one event category."""

    def __init__(
        self,
        name: str,
        *,
        action_shortcut: bool = False,
        cloud_type_shortcut: bool = False,
    ) -> None:
        self.name = name
        self._action_shortcut = action_shortcut
        self._cloud_type_shortcut = cloud_type_shortcut
        self._handlers: list[HandlerObject] = []

    @property
    def handlers(self) -> tuple[HandlerObject, ...]:
        """Return a stable registration snapshot."""
        return tuple(self._handlers)

    def register(
        self, callback: HandlerCallback, *filters: FilterLike | str
    ) -> HandlerCallback:
        """Register and return ``callback`` for programmatic use."""
        normalized = tuple(self._normalize_filter(filter_) for filter_ in filters)
        self._handlers.append(HandlerObject(callback=callback, filters=normalized))
        return callback

    def __call__(
        self, *filters: FilterLike | str
    ) -> Callable[[HandlerCallback], HandlerCallback]:
        """Create a handler-registration decorator."""

        def decorator(callback: HandlerCallback) -> HandlerCallback:
            return self.register(callback, *filters)

        return decorator

    def _normalize_filter(self, filter_: FilterLike | str) -> FilterLike:
        if isinstance(filter_, str):
            if self._action_shortcut:
                return F.name == filter_
            if self._cloud_type_shortcut:
                return F.cloud_type == filter_
            raise TypeError(
                f"String filter shortcuts are not supported by {self.name!r}"
            )
        if not callable(filter_):
            raise TypeError(
                "Filters must be asynchronous callables or magic expressions"
            )
        return filter_

    def __len__(self) -> int:
        return len(self._handlers)

    def __repr__(self) -> str:
        return f"EventObserver(name={self.name!r}, handlers={len(self)})"


__all__ = ["EventObserver"]
