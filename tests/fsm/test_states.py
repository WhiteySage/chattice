"""State and StatesGroup."""

from __future__ import annotations

from chattice.fsm.states import State, StatesGroup


class Incident(StatesGroup):
    title = State()
    severity = State()
    confirmation = State()


def test_state_string_keys() -> None:
    assert Incident.title.state == "Incident:title"
    assert Incident.severity.state == "Incident:severity"


def test_custom_state_key() -> None:
    assert State(state="custom:key").state == "custom:key"


def test_all_states_declaration_order() -> None:
    assert list(Incident.__all_states__) == ["title", "severity", "confirmation"]


def test_all_states_values_are_the_same_instances() -> None:
    assert Incident.__all_states__["title"] is Incident.title


def test_groups_are_independent() -> None:
    class Other(StatesGroup):
        title = State()

    assert Other.title.state == "Other:title"
    assert Other.title is not Incident.title
