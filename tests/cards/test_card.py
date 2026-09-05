"""Card, CardHeader, Section facades."""

from __future__ import annotations

from chattice.cards import (
    Button,
    ButtonList,
    Card,
    CardHeader,
    DateTimePicker,
    Divider,
    RawWidget,
    Section,
    SelectionInput,
    TextInput,
    TextParagraph,
)


def test_header() -> None:
    proto = CardHeader(title="Deploy production?", subtitle="v2.1").to_proto()
    assert proto["title"] == "Deploy production?"
    assert proto["subtitle"] == "v2.1"


def test_section_builds_widgets() -> None:
    section = Section(
        header="Actions",
        widgets=[TextParagraph("Deploy?"), Divider()],
    ).to_proto_dict()
    assert section["header"] == "Actions"
    assert section["widgets"][0]["text_paragraph"]["text"] == "Deploy?"
    assert section["widgets"][1] == {"divider": {}}


def test_card_full() -> None:
    card = Card(
        header=CardHeader(title="Deploy production?"),
        sections=[
            Section(
                widgets=[
                    TextParagraph("Deploy v2.1 to prod?"),
                    ButtonList(
                        buttons=[
                            Button(
                                "Deploy",
                                action="deploy.confirm",
                                parameters={"env": "prod"},
                            ),
                            Button("Cancel", action="deploy.cancel"),
                        ]
                    ),
                ]
            )
        ],
    )
    proto = card.to_proto()
    assert proto.header.title == "Deploy production?"
    assert proto.sections[0].widgets[1].button_list.buttons[0].text == "Deploy"


def test_card_to_dict_and_back() -> None:
    card = Card(
        header=CardHeader(title="T"),
        sections=[Section(widgets=[TextParagraph("hi")])],
    )
    data = card.to_dict()
    assert data["header"]["title"] == "T"
    assert Card.from_dict(data) == card
    assert Card.from_proto(card.to_proto()) == card


def test_section_form_widgets_dispatch() -> None:
    section = Section(
        widgets=[
            TextInput(name="env", label="Environment"),
            SelectionInput(
                name="mode",
                label="Mode",
                items=[{"text": "prod", "value": "prod"}],
            ),
            DateTimePicker(name="when", label="When"),
        ]
    ).to_proto_dict()
    assert section["widgets"][0]["text_input"]["name"] == "env"
    assert section["widgets"][1]["selection_input"]["items"][0]["text"] == "prod"
    assert section["widgets"][2]["date_time_picker"]["label"] == "When"


def test_bare_button_widget_is_rejected() -> None:
    import pytest

    from chattice.cards import Button

    with pytest.raises(TypeError):
        Section(widgets=[Button("X", action="a.b")]).to_proto_dict()  # type: ignore[list-item]


def test_unmodelled_proto_widget_becomes_raw_widget() -> None:
    from google.apps.card_v1.types.card import Grid

    card = Card(sections=[Section(widgets=[TextInput(name="env", label="E")])])
    proto = card.to_proto()
    # The facade models a fixed set of the SDK's widget kinds; an
    # unmodelled kind is retained through the raw fallback.
    proto.sections[0].widgets[0].grid = Grid()
    rebuilt = Card.from_proto(proto)
    assert isinstance(rebuilt.sections[0].widgets[0], RawWidget)
    assert rebuilt.sections[0].widgets[0].to_dict() == {"grid": {}}


def test_button_options_round_trip() -> None:
    card = Card(
        sections=[
            Section(
                widgets=[
                    ButtonList(
                        buttons=[
                            Button("X", action="a.b", disabled=True, alt_text="alt")
                        ]
                    )
                ]
            )
        ]
    )
    assert Card.from_dict(card.to_dict()) == card
