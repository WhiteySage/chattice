"""Widget facade builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from google.apps.card_v1.types.card import Button as ProtoButton
from google.apps.card_v1.types.card import ButtonList as ProtoButtonList
from google.apps.card_v1.types.card import DateTimePicker as ProtoDateTimePicker
from google.apps.card_v1.types.card import Divider as ProtoDivider
from google.apps.card_v1.types.card import SelectionInput as ProtoSelectionInput
from google.apps.card_v1.types.card import TextInput as ProtoTextInput
from google.apps.card_v1.types.card import TextParagraph as ProtoTextParagraph

from chattice.actions import ActionData

from .actions import Action
from .validation import Validation

__all__ = [
    "Button",
    "ButtonInteraction",
    "ButtonList",
    "ButtonType",
    "DateTimePicker",
    "Divider",
    "SelectionInput",
    "TextInput",
    "TextParagraph",
]


class ButtonInteraction:
    """Documented action.interaction values."""

    OPEN_DIALOG = "OPEN_DIALOG"


@dataclass(frozen=True, slots=True)
class TextParagraph:
    """A paragraph of text."""

    text: str
    max_lines: int | None = None

    def to_proto(self) -> ProtoTextParagraph:
        kwargs: dict[str, Any] = {"text": self.text}
        if self.max_lines is not None:
            kwargs["max_lines"] = self.max_lines
        return ProtoTextParagraph(**kwargs)


@dataclass(frozen=True, slots=True)
class Divider:
    """A horizontal divider between widgets."""

    def to_proto(self) -> ProtoDivider:
        return ProtoDivider()


class ButtonType:
    """Documented Button.type values (Google Chat apps only).

    https://developers.google.com/workspace/chat/api/reference/rest/v1/cards#button
    """

    OUTLINED = "OUTLINED"  # default when unset
    FILLED = "FILLED"  # primary action, most visual impact
    FILLED_TONAL = "FILLED_TONAL"  # middle ground between filled and outlined
    BORDERLESS = "BORDERLESS"  # lowest priority


@dataclass(frozen=True, slots=True)
class Button:
    """A clickable button: either an action or a link."""

    text: str
    action: str | ActionData | None = None
    interaction: str | None = None
    parameters: Mapping[str, str] = field(default_factory=dict)
    open_link: str | None = None
    # SDK accepts a google.type.Color instance or an RGB mapping
    # (e.g. {"red": 1.0, "green": 0.0, "blue": 0.0}).
    color: Any = None
    # Documented Button.type: OUTLINED/FILLED/FILLED_TONAL/BORDERLESS
    # (Chat apps only). Unset -> Google defaults to OUTLINED; when
    # ``color`` is set Google forces FILLED and ignores this value.
    type: str | None = None
    disabled: bool = False
    alt_text: str | None = None
    required_widgets: tuple[str, ...] = ()
    persist_values: bool = False
    load_indicator: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.action, ActionData):
            if self.action.function is None:
                raise ValueError(
                    "Button ActionData requires a Google action function; "
                    "declare the model as class Deploy(ActionData, "
                    "function='deploy')"
                )
            if self.parameters:
                raise ValueError(
                    "Button parameters must be omitted when action is ActionData"
                )
            object.__setattr__(self, "parameters", self.action.to_parameters())
            object.__setattr__(self, "action", self.action.function)
        # exactly one of action/open_link — a button with both used
        # to silently prefer the action; neither only failed at
        # serialization. Fail at construction instead.
        if self.action is not None and self.open_link is not None:
            raise ValueError(
                "Button accepts either an action or an open link, not both"
            )
        object.__setattr__(self, "required_widgets", tuple(self.required_widgets))
        # Snapshot mutable mappings so the frozen facade cannot change
        # after validation.
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_proto(self) -> ProtoButton:
        if self.action is not None:
            action: dict[str, Any] = {
                "function": self.action,
                "parameters": [
                    {"key": key, "value": value}
                    for key, value in self.parameters.items()
                ],
            }
            if self.interaction is not None:
                action["interaction"] = self.interaction
            if self.required_widgets:
                action["required_widgets"] = list(self.required_widgets)
            if self.persist_values:
                action["persist_values"] = True
            # the SDK LoadIndicator enum has NO unspecified value
            # (SPINNER == 0 == unset), so write NONE explicitly — the
            # round-trip through the wire otherwise cannot tell "unset"
            # apart from "SPINNER".
            action["load_indicator"] = "SPINNER" if self.load_indicator else "NONE"
            on_click = {"action": action}
        elif self.open_link is not None:
            on_click = {"open_link": {"url": self.open_link}}
        else:
            raise ValueError("Button requires 'action' or 'open_link'")
        kwargs: dict[str, Any] = {
            "text": self.text,
            "on_click": on_click,
            "disabled": self.disabled,
        }
        if self.color is not None:
            kwargs["color"] = self.color
        if self.type is not None:
            kwargs["type"] = self.type
        if self.alt_text is not None:
            kwargs["alt_text"] = self.alt_text
        return ProtoButton(**kwargs)


@dataclass(frozen=True, slots=True)
class ButtonList:
    """A horizontal row of buttons."""

    buttons: Sequence[Button] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Canonicalize the container so round-trips compare equal
        # regardless of whether the caller passed a list or a tuple.
        object.__setattr__(self, "buttons", tuple(self.buttons))

    def to_proto(self) -> ProtoButtonList:
        return ProtoButtonList(buttons=[b.to_proto() for b in self.buttons])


@dataclass(frozen=True, slots=True)
class TextInput:
    """A text input field."""

    name: str
    label: str
    hint_text: str | None = None
    value: str | None = None
    validation: Validation | None = None

    def to_proto(self) -> ProtoTextInput:
        kwargs: dict[str, Any] = {"name": self.name, "label": self.label}
        if self.hint_text is not None:
            kwargs["hint_text"] = self.hint_text
        if self.value is not None:
            kwargs["value"] = self.value
        if self.validation is not None:
            kwargs["validation"] = self.validation.to_proto()
        return ProtoTextInput(**kwargs)


@dataclass(frozen=True, slots=True)
class SelectionInput:
    """A selection field.

    NOTE: the installed SDK proto (google-apps-card 0.7.0) has no default-
    selection field, so the facade models exactly what the SDK supports.
    """

    name: str
    label: str
    items: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    # Dynamic selections (enterprise autocomplete): Google's
    # external-data-source is an ACTION (a function the app serves for
    # suggestions) — the datasource logic itself is application code.
    external_data_source: Action | None = None
    multi_select_max_selected_items: int | None = None
    multi_select_min_query_length: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))

    def to_proto(self) -> ProtoSelectionInput:
        kwargs: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "items": [dict(item) for item in self.items],
        }
        if self.external_data_source is not None:
            kwargs["external_data_source"] = self.external_data_source.to_proto()
        if self.multi_select_max_selected_items is not None:
            kwargs["multi_select_max_selected_items"] = (
                self.multi_select_max_selected_items
            )
        if self.multi_select_min_query_length is not None:
            kwargs["multi_select_min_query_length"] = self.multi_select_min_query_length
        return ProtoSelectionInput(**kwargs)


@dataclass(frozen=True, slots=True)
class DateTimePicker:
    """A date/time picker."""

    name: str
    label: str
    value_ms_epoch: int | None = None
    timezone_offset_date: int | None = None

    def to_proto(self) -> ProtoDateTimePicker:
        kwargs: dict[str, Any] = {"name": self.name, "label": self.label}
        if self.value_ms_epoch is not None:
            kwargs["value_ms_epoch"] = self.value_ms_epoch
        if self.timezone_offset_date is not None:
            kwargs["timezone_offset_date"] = self.timezone_offset_date
        return ProtoDateTimePicker(**kwargs)
