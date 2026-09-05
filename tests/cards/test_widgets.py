"""Widget facades."""

from __future__ import annotations

import pytest

from chattice.cards import (
    Button,
    ButtonList,
    ButtonType,
    DateTimePicker,
    Divider,
    SelectionInput,
    TextInput,
    TextParagraph,
)


def test_text_paragraph() -> None:
    proto = TextParagraph("Deploy v2.1?", max_lines=2).to_proto()
    assert proto.text == "Deploy v2.1?"
    assert proto.max_lines == 2


def test_divider() -> None:
    proto = Divider().to_proto()
    assert proto is not None  # empty proto message


def test_button_with_action() -> None:
    button = Button(
        "Deploy", action="deploy.confirm", parameters={"env": "prod"}
    ).to_proto()
    assert button.text == "Deploy"
    assert button.on_click.action.function == "deploy.confirm"
    assert [(p.key, p.value) for p in button.on_click.action.parameters] == [
        ("env", "prod")
    ]


def test_button_with_open_link() -> None:
    button = Button("Docs", open_link="https://example.com").to_proto()
    assert button.text == "Docs"
    assert button.on_click.open_link.url == "https://example.com"


def test_button_options() -> None:
    button = Button(
        "X",
        action="a.b",
        color={"red": 1.0, "green": 0.0, "blue": 0.0},
        disabled=True,
        alt_text="alt",
    ).to_proto()
    assert button.color.red == 1.0
    assert button.disabled is True
    assert button.alt_text == "alt"


def test_button_type_serializes_documented_values() -> None:
    """Button.type is a documented Chat-only field (OUTLINED default;
    FILLED / FILLED_TONAL / BORDERLESS). Unset -> not sent (proto keeps
    TYPE_UNSPECIFIED)."""
    default = Button("X", action="a.b").to_proto()
    assert default.type.name == "TYPE_UNSPECIFIED"  # unset — not sent
    tonal = Button("X", action="a.b", type=ButtonType.FILLED_TONAL).to_proto()
    assert tonal.type.name == "FILLED_TONAL"
    assert ButtonType.FILLED == "FILLED"
    assert ButtonType.BORDERLESS == "BORDERLESS"


def test_button_requires_action_or_link() -> None:
    with pytest.raises(ValueError):
        Button("Bare").to_proto()


def test_button_list() -> None:
    buttons = [
        Button("Deploy", action="deploy.confirm", parameters={"env": "prod"}),
        Button("Cancel", action="deploy.cancel"),
    ]
    proto = ButtonList(buttons).to_proto()
    assert [b.text for b in proto.buttons] == ["Deploy", "Cancel"]
    assert proto.buttons[0].on_click.action.function == "deploy.confirm"


def test_text_input_minimal() -> None:
    proto = TextInput(name="env", label="Environment").to_proto()
    assert proto.name == "env"
    assert proto.label == "Environment"


def test_selection_input_minimal() -> None:
    proto = SelectionInput(
        name="env", label="Env", items=[{"text": "prod", "value": "prod"}]
    ).to_proto()
    assert proto.name == "env"
    assert proto.items[0].text == "prod"


def test_date_time_picker_minimal() -> None:
    proto = DateTimePicker(name="when", label="When").to_proto()
    assert proto.name == "when"
    assert proto.label == "When"


def test_button_required_widgets() -> None:
    from chattice.cards import Button

    button = Button("Go", action="x", required_widgets=("name", "email"))
    proto = button.to_proto()
    assert list(proto.on_click.action.required_widgets) == ["name", "email"]
