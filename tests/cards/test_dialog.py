"""Dialog facade."""

from __future__ import annotations

from chattice.cards import Card, CardHeader, Dialog, Section, TextParagraph


def test_dialog_builds_sdk_proto() -> None:
    card = Card(
        header=CardHeader(title="New contact"),
        sections=[Section(widgets=[TextParagraph("Enter details")])],
    )
    dialog = Dialog(body=card)
    proto = dialog.to_proto()
    assert proto.body.header.title == "New contact"


def test_dialog_to_dict_shape() -> None:
    card = Card(header=CardHeader(title="T"))
    data = Dialog(body=card).to_dict()
    assert data["dialog"]["body"]["header"]["title"] == "T"


def test_equality() -> None:
    card = Card(header=CardHeader(title="T"))
    assert Dialog(body=card) == Dialog(body=card)
