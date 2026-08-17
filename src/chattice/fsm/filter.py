"""StateFilter: declarative routing by the current FSM state."""

from __future__ import annotations

from collections.abc import Mapping

from chattice.events import Event
from chattice.filters.base import BaseFilter, FilterValue

from .context import FSMContext
from .states import State

__all__ = ["StateFilter"]


class StateFilter(BaseFilter):
    """Matches when the event's current FSM state is one of the given states.

    An empty filter matches ANY non-None state. Without an FSM context in
    the filter context (dispatcher configured without fsm_storage) it never
    matches.
    """

    def __init__(self, *states: State) -> None:
        self._states = {state.state for state in states}

    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        del event
        state = context.get("state")
        if not isinstance(state, FSMContext):
            return False
        current = await state.get_state()
        if current is None:
            return False
        if not self._states:
            return True
        return current in self._states
