"""Button interaction and full form widget fields."""

from __future__ import annotations

from chattice.cards import (
    Button,
    ButtonInteraction,
    DateTimePicker,
    SelectionInput,
    TextInput,
    TextInputType,
    Validation,
)


def test_button_open_dialog_interaction() -> None:
    proto = Button(
        "Add", action="open.contact", interaction=ButtonInteraction.OPEN_DIALOG
    ).to_proto()
    assert proto.on_click.action.function == "open.contact"
    # SDK (google-apps-card 0.7.0) exposes interaction as an enum member,
    # so compare the member's name against the documented wire value.
    assert proto.on_click.action.interaction.name == "OPEN_DIALOG"


def test_button_without_interaction_omits_it() -> None:
    proto = Button("Plain", action="a.b").to_proto()
    # Unset enum field defaults to the SDK's zero-value member,
    # not an empty string.
    assert proto.on_click.action.interaction.name == "INTERACTION_UNSPECIFIED"


def test_text_input_full_fields() -> None:
    proto = TextInput(
        name="name",
        label="Имя",
        hint_text="Как к вам обращаться",
        value="Иван",
        validation=Validation(character_limit=50, input_type=TextInputType.TEXT),
    ).to_proto()
    assert proto.name == "name"
    assert proto.label == "Имя"
    assert proto.hint_text == "Как к вам обращаться"
    assert proto.value == "Иван"
    assert proto.validation.character_limit == 50


def test_selection_input_full_fields() -> None:
    # NOTE: SDK 0.7.0's SelectionInput proto has no default-selection field,
    # so the facade models exactly what the SDK supports (no `value`).
    proto = SelectionInput(
        name="env",
        label="Environment",
        items=[{"text": "prod", "value": "prod"}, {"text": "dev", "value": "dev"}],
    ).to_proto()
    assert proto.name == "env"
    assert [i.value for i in proto.items] == ["prod", "dev"]


def test_date_time_picker_full_fields() -> None:
    proto = DateTimePicker(
        name="when",
        label="When",
        value_ms_epoch=1_700_000_000_000,
        timezone_offset_date=0,
    ).to_proto()
    assert proto.value_ms_epoch == 1_700_000_000_000
    assert proto.timezone_offset_date == 0
