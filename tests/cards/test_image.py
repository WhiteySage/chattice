"""Typed Cards v2 Image widget."""

from __future__ import annotations

import pytest

from chattice.cards import Action, Card, Image, OpenLink, Section


def test_image_to_proto() -> None:
    proto = Image(image_url="https://example.com/r.png", alt_text="Result").to_proto()
    assert proto.image_url == "https://example.com/r.png"
    assert proto.alt_text == "Result"


def test_image_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        Image(image_url="http://example.com/a.png")
    with pytest.raises(ValueError, match="HTTPS"):
        Image(image_url="/local/a.png")
    with pytest.raises(ValueError, match="HTTPS"):
        Image(image_url="data:image/png;base64,xxx")
    with pytest.raises(ValueError, match="HTTPS"):
        Image(image_url="file:///tmp/a.png")


def test_image_on_click_action_and_link() -> None:
    action_proto = Image(
        image_url="https://e.com/i.png", on_click=Action(function="go")
    ).to_proto()
    assert action_proto.on_click.action.function == "go"
    link_proto = Image(
        image_url="https://e.com/i.png", on_click=OpenLink(url="https://e.com/x")
    ).to_proto()
    assert link_proto.on_click.open_link.url == "https://e.com/x"


def test_card_proto_roundtrip_with_image() -> None:
    card = Card(
        sections=[
            Section(
                widgets=[
                    Image(
                        image_url="https://e.com/i.png",
                        alt_text="A",
                        on_click=Action(function="go"),
                    )
                ]
            )
        ]
    )
    back = Card.from_proto(card.to_proto())
    widget = back.sections[0].widgets[0]
    assert isinstance(widget, Image)
    assert widget.image_url == "https://e.com/i.png"
    assert widget.alt_text == "A"
    assert isinstance(widget.on_click, Action)
    assert widget.on_click.function == "go"


def test_card_dict_roundtrip_with_image() -> None:
    card = Card(sections=[Section(widgets=[Image(image_url="https://e.com/i.png")])])
    back = Card.from_dict(card.to_dict())
    widget = back.sections[0].widgets[0]
    assert isinstance(widget, Image)  # not demoted to RawWidget
    assert widget.image_url == "https://e.com/i.png"
