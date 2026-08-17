"""Card assertions and the FSM seeding helper."""

from __future__ import annotations

import pytest

from chattice.cards import Button, ButtonList, Card, CardHeader, Section
from chattice.fsm import FSMContext, MemoryStorage, StateFilter, StorageKey
from chattice.fsm.states import State, StatesGroup
from chattice.testing import (
    EventFactory,
    assert_card_has_button,
    assert_card_header,
    set_state_for,
)


class Incident(StatesGroup):
    title = State()


def _card() -> Card:
    return Card(
        header=CardHeader(title="Deploy?"),
        sections=[
            Section(
                widgets=[
                    ButtonList(buttons=[Button("Deploy", action="deploy.confirm")])
                ]
            )
        ],
    )


def test_card_button_assertion_passes() -> None:
    assert_card_has_button(_card(), action="deploy.confirm", text="Deploy")


def test_card_button_assertion_fails() -> None:
    with pytest.raises(AssertionError, match="cancel"):
        assert_card_has_button(_card(), action="deploy.cancel")


def test_card_header_assertion() -> None:
    assert_card_header(_card(), title="Deploy?")
    with pytest.raises(AssertionError, match="Other"):
        assert_card_header(_card(), title="Other")


async def test_set_state_for_seeds_state() -> None:
    storage = MemoryStorage()
    key = StorageKey(user="users/1", space="spaces/A", thread=None)
    await set_state_for(storage, key, Incident.title)
    context = FSMContext(storage, key)
    filter_ = StateFilter(Incident.title)
    assert await filter_(EventFactory.message("x"), {"state": context})
