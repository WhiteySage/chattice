"""to_dict -> from_dict -> equal facades (the raw escape hatch path too)."""

from __future__ import annotations

from chattice.cards import (
    Button,
    ButtonList,
    Card,
    CardHeader,
    Divider,
    RawWidget,
    Section,
    TextParagraph,
)


def test_round_trip_preserves_facade() -> None:
    card = Card(
        header=CardHeader(title="Deploy", subtitle="v2"),
        sections=[
            Section(
                header="Actions",
                widgets=[
                    TextParagraph("Proceed?"),
                    Divider(),
                    ButtonList(
                        buttons=[
                            Button(
                                "Yes",
                                action="deploy.confirm",
                                parameters={"env": "prod"},
                            ),
                            Button("No", action="deploy.cancel"),
                        ]
                    ),
                ],
            )
        ],
    )
    assert Card.from_dict(card.to_dict()) == card


def test_raw_proto_escape_hatch() -> None:
    card = Card(header=CardHeader(title="T")).to_proto()
    # Any future Google field/widget passes through the proto unchanged
    # (PEEK is DisplayStyle value 1; the proto stub types the enum as int).
    card.display_style = 1  # type: ignore[assignment]
    assert card.display_style == 1


def test_unknown_widgets_and_fields_round_trip_losslessly() -> None:
    data = {
        "name": "future-card",
        "futureTopLevel": {"kept": [1, 2, 3]},
        "header": {"title": "T", "futureHeaderField": "kept"},
        "sections": [
            {
                "header": "S",
                "futureSectionField": True,
                "widgets": [
                    {"decoratedText": {"text": "SDK-known but facade-unmodelled"}},
                    {"futureWidget": {"nested": {"kept": "yes"}}},
                ],
            }
        ],
    }

    card = Card.from_dict(data)

    assert all(isinstance(widget, RawWidget) for widget in card.sections[0].widgets)
    assert card.to_dict() == data


def test_unknown_field_on_known_widget_is_preserved_by_card_round_trip() -> None:
    data = {
        "sections": [
            {
                "widgets": [
                    {
                        "textParagraph": {
                            "text": "known",
                            "futureTextField": {"kept": True},
                        },
                        "futureWidgetEnvelopeField": "kept",
                    }
                ]
            }
        ]
    }

    assert Card.from_dict(data).to_dict() == data
