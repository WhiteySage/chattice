"""Registered handler representation."""

from __future__ import annotations

from dataclasses import dataclass, field

from chattice.exceptions import InvalidHandlerError
from chattice.filters import FilterLike

from .dependency import HandlerCallback, HandlerPlan, build_handler_plan


@dataclass(frozen=True, slots=True)
class HandlerObject:
    """A callback, its filters, and its cached dependency plan."""

    callback: HandlerCallback
    filters: tuple[FilterLike, ...]
    plan: HandlerPlan = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            plan = build_handler_plan(self.callback)
        except TypeError as error:
            raise InvalidHandlerError(
                "Handlers must be hashable so their plans can be cached"
            ) from error
        object.__setattr__(self, "plan", plan)
