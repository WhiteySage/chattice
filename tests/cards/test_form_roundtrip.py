"""Form widgets round-trip through Section.from_proto (Phase 5 debt closed)."""

from __future__ import annotations

from chattice.cards import (
    Card,
    DateTimePicker,
    Section,
    SelectionInput,
    TextInput,
    TextInputType,
    Validation,
)


def test_form_widgets_round_trip() -> None:
    card = Card(
        sections=[
            Section(
                widgets=[
                    TextInput(
                        name="name",
                        label="Имя",
                        hint_text="Как вас зовут",
                        value="Иван",
                        validation=Validation(
                            character_limit=50, input_type=TextInputType.TEXT
                        ),
                    ),
                    SelectionInput(
                        name="env",
                        label="Environment",
                        items=[{"text": "prod", "value": "prod"}],
                    ),
                    DateTimePicker(
                        name="when", label="When", value_ms_epoch=1_700_000_000_000
                    ),
                ]
            )
        ]
    )
    assert Card.from_dict(card.to_dict()) == card


def test_open_dialog_button_round_trip_preserves_interaction() -> None:
    from chattice.cards import Button, ButtonInteraction, ButtonList

    card = Card(
        sections=[
            Section(
                widgets=[
                    ButtonList(
                        buttons=[
                            Button(
                                "Open",
                                action="open.contact",
                                interaction=ButtonInteraction.OPEN_DIALOG,
                            )
                        ]
                    )
                ]
            )
        ]
    )
    assert Card.from_dict(card.to_dict()) == card
