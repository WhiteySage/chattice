"""F11 regression: enum codec, App Home form reuse, card round-trip."""

from __future__ import annotations

import dataclasses
from enum import Enum, IntEnum

import pytest

from chattice.actions import ActionData, ActionDataDecodeError
from chattice.events import FormInputs, FormSubmitEvent, StringInput
from chattice.forms import FormModel

# ------------------------------------------------------------ enum codec


class _Priority(Enum):
    LOW = "low"
    HIGH = "high"


class _Level(IntEnum):
    ONE = 1
    TWO = 2


@dataclasses.dataclass
class _Deploy(ActionData):
    priority: _Priority
    level: _Level = _Level.ONE


def test_string_enum_roundtrip() -> None:
    data = _Deploy(priority=_Priority.HIGH, level=_Level.TWO)
    decoded = _Deploy.from_parameters(data.to_parameters())
    assert decoded.priority is _Priority.HIGH
    assert decoded.level is _Level.TWO


def test_numeric_enum_roundtrip() -> None:
    """The audit's probe: numeric Enum values used to raise
    ActionDataDecodeError on decode."""
    data = _Deploy(priority=_Priority.LOW, level=_Level.ONE)
    decoded = _Deploy.from_parameters(data.to_parameters())
    assert decoded.level is _Level.ONE  # value 1 round-trips


def test_enum_decode_unknown_value_raises() -> None:
    with pytest.raises(ActionDataDecodeError):
        _Deploy.from_parameters({"priority": "medium", "level": "1"})


def test_enum_decode_returns_self() -> None:
    decoded = _Deploy.from_parameters({"priority": "high", "level": "2"})
    assert isinstance(decoded, _Deploy)


# ---------------------------------------------- App Home form reuse (F11)


@dataclasses.dataclass
class _ContactForm(FormModel):
    name: StringInput


def test_form_filter_accepts_app_home_form_submit() -> None:
    """The same typed form model works on dialog submits AND App Home."""
    filter_ = _ContactForm.filter()
    import asyncio

    async def run() -> dict[str, object]:
        event = FormSubmitEvent(
            function_name="contact.submit",
            form_inputs=FormInputs(data={"name": StringInput(values=("Kai",))}),
        )
        result = await filter_(event, {})
        assert isinstance(result, dict)
        return result

    result = asyncio.run(run())
    assert isinstance(result["form"], _ContactForm)
    assert result["form"].name.values == ("Kai",)


def test_form_filter_rejects_wrong_shape() -> None:
    import asyncio

    filter_ = _ContactForm.filter()

    async def run() -> object:
        event = FormSubmitEvent(function_name="x", form_inputs=FormInputs(data={}))
        return await filter_(event, {})

    assert asyncio.run(run()) is False


# ------------------------------------------------- card round-trip (F11)


def test_card_roundtrip_preserves_button_and_selection_fields() -> None:
    from chattice.cards import (
        Action,
        Button,
        ButtonList,
        Card,
        CardHeader,
        Section,
        SelectionInput,
    )

    card = Card(
        header=CardHeader(title="T"),
        sections=[
            Section(
                widgets=[
                    ButtonList(
                        buttons=[
                            Button(
                                "Go",
                                action="f.go",
                                required_widgets=("a", "b"),
                                persist_values=True,
                                load_indicator=True,
                                type="FILLED_TONAL",
                            )
                        ]
                    ),
                    SelectionInput(
                        name="emp",
                        label="Employee",
                        items=({"text": "Kai", "value": "1"},),
                        external_data_source=Action(function="employee.search"),
                        multi_select_max_selected_items=3,
                        multi_select_min_query_length=2,
                    ),
                ]
            )
        ],
    )
    rebuilt = Card.from_dict(card.to_dict())
    assert rebuilt == card


def test_card_roundtrip_no_load_indicator_stays_false() -> None:
    from chattice.cards import Button, ButtonList, Card, Section

    card = Card(
        sections=[Section(widgets=[ButtonList(buttons=[Button("x", action="a")])])]
    )
    rebuilt = Card.from_dict(card.to_dict())
    buttons = rebuilt.sections[0].widgets[0]
    assert isinstance(buttons, ButtonList)
    assert buttons.buttons[0].load_indicator is False
    assert rebuilt == card
