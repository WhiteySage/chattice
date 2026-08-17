"""Proto <-> documented Cards v2 JSON helpers."""

from __future__ import annotations

from google.apps.card_v1.types.card import Card

from chattice.cards.serialization import from_dict, to_dict


def _card() -> Card:
    return Card(
        header={"title": "Deploy production?"},
        sections=[
            {
                "header": "S1",
                "widgets": [{"text_paragraph": {"text": "Deploy v2.1?"}}],
            }
        ],
    )


def test_to_dict_is_documented_camel_case() -> None:
    data = to_dict(_card())
    assert data["header"] == {"title": "Deploy production?"}
    assert data["sections"][0]["widgets"][0] == {
        "textParagraph": {"text": "Deploy v2.1?"}
    }


def test_from_dict_round_trips() -> None:
    card = _card()
    rebuilt = from_dict(to_dict(card))
    assert rebuilt.header.title == "Deploy production?"
    assert rebuilt.sections[0].widgets[0].text_paragraph.text == "Deploy v2.1?"
