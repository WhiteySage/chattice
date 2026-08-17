"""FSM seeding helpers for tests."""

from __future__ import annotations

from chattice.fsm.states import State
from chattice.fsm.storage import BaseStorage, StorageKey

__all__ = ["set_state_for"]


async def set_state_for(storage: BaseStorage, key: StorageKey, state: State) -> None:
    """Seed a workflow state (the Phase 7 gate pattern)."""
    await storage.set_state(key, state.state)
