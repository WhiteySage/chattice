"""Card assertion helpers with actionable messages."""

from __future__ import annotations

from chattice.cards import Button, ButtonList, Card

__all__ = ["assert_card_has_button", "assert_card_header"]


def _buttons(card: Card) -> list[Button]:
    found: list[Button] = []
    for section in card.sections:
        for widget in section.widgets:
            if isinstance(widget, ButtonList):
                found.extend(widget.buttons)
    return found


def assert_card_has_button(
    card: Card, *, action: str | None = None, text: str | None = None
) -> None:
    """Assert the card contains a button matching the given action/text."""
    buttons = _buttons(card)
    for button in buttons:
        if action is not None and button.action != action:
            continue
        if text is not None and button.text != text:
            continue
        return
    wanted = f"action={action!r}" if action else f"text={text!r}"
    raise AssertionError(f"no button with {wanted} found on the card")


def assert_card_header(
    card: Card, *, title: str | None = None, subtitle: str | None = None
) -> None:
    """Assert the card header matches the given fields."""
    header = card.header
    if header is None:
        raise AssertionError("card has no header")
    if title is not None and header.title != title:
        raise AssertionError(f"expected header title {title!r}, got {header.title!r}")
    if subtitle is not None and header.subtitle != subtitle:
        raise AssertionError(
            f"expected header subtitle {subtitle!r}, got {header.subtitle!r}"
        )
