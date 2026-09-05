"""Widget facade builders."""

from __future__ import annotations

import mimetypes
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urlparse

from google.apps.card_v1.types.card import Button as ProtoButton
from google.apps.card_v1.types.card import ButtonList as ProtoButtonList
from google.apps.card_v1.types.card import DateTimePicker as ProtoDateTimePicker
from google.apps.card_v1.types.card import Divider as ProtoDivider
from google.apps.card_v1.types.card import Image as ProtoImage
from google.apps.card_v1.types.card import SelectionInput as ProtoSelectionInput
from google.apps.card_v1.types.card import TextInput as ProtoTextInput
from google.apps.card_v1.types.card import TextParagraph as ProtoTextParagraph

from chattice.actions import ActionData

from .actions import Action, OpenLink
from .validation import Validation

_SUPPORTED_LOCAL_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})


@dataclass(frozen=True, slots=True)
class _PathImageSource:
    path: Path
    filename: str
    content_type: str
    namespace: str | None


@dataclass(frozen=True, slots=True)
class _BytesImageSource:
    data: bytes
    filename: str
    content_type: str
    namespace: str | None


_LocalImageSource: TypeAlias = _PathImageSource | _BytesImageSource


def _filename(value: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value or "\\" in value:
        raise ValueError("filename must be a non-empty basename without directories")
    return value


def _content_type(filename: str, explicit: str | None) -> str:
    content_type = explicit or mimetypes.guess_type(filename)[0]
    if content_type is None:
        raise ValueError(
            "content_type could not be inferred from filename; pass it explicitly"
        )
    content_type = content_type.lower().strip()
    if content_type not in _SUPPORTED_LOCAL_IMAGE_TYPES:
        raise ValueError("Local Card images must be PNG or JPEG")
    return content_type


def _namespace(value: str | None) -> str | None:
    if value is None:
        return None
    if not value or value != value.strip() or "/" in value or "\\" in value:
        raise ValueError(
            "namespace must be a non-empty logical name, not a storage path"
        )
    return value


__all__ = [
    "Button",
    "ButtonInteraction",
    "ButtonList",
    "ButtonType",
    "DateTimePicker",
    "Divider",
    "Image",
    "SelectionInput",
    "TextInput",
    "TextParagraph",
]


@dataclass(frozen=True, slots=True)
class Image:
    """A URL or lazily published local picture rendered inside a Card.

    Card Image is a URL-based UI widget — the other Google media surface
    (a local file uploaded as a Chat attachment) is
    ``chattice.media.InputFile``. ``from_path`` and ``from_bytes`` require
    an AssetPublisher on the Bot that sends or updates the Card.
    """

    image_url: str | None
    alt_text: str | None = None
    on_click: Action | OpenLink | None = None
    _local_source: _LocalImageSource | None = field(
        default=None, init=False, repr=False, compare=True
    )

    def __post_init__(self) -> None:
        if self.image_url is None:
            raise ValueError("Image requires an absolute HTTPS URL")
        self._validate_url(self.image_url)
        self._snapshot_action()

    @staticmethod
    def _validate_url(image_url: str) -> None:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(
                "Image.image_url must be an absolute HTTPS URL; local "
                "paths, bytes and data: URLs require Image.from_path() "
                "or Image.from_bytes()"
            )

    def _snapshot_action(self) -> None:
        if isinstance(self.on_click, Action):
            # Snapshot mutable parameters so the frozen facade cannot
            # change after validation.
            object.__setattr__(
                self,
                "on_click",
                Action(
                    function=self.on_click.function,
                    parameters=dict(self.on_click.parameters),
                    interaction=self.on_click.interaction,
                ),
            )

    @classmethod
    def from_url(
        cls,
        image_url: str,
        *,
        alt_text: str | None = None,
        on_click: Action | OpenLink | None = None,
    ) -> Image:
        """Build an Image from an already published HTTPS URL."""
        return cls(image_url=image_url, alt_text=alt_text, on_click=on_click)

    @classmethod
    def from_path(
        cls,
        path: str | PathLike[str],
        *,
        filename: str | None = None,
        content_type: str | None = None,
        namespace: str | None = None,
        alt_text: str | None = None,
        on_click: Action | OpenLink | None = None,
    ) -> Image:
        """Build a lazy local Image without reading the file."""
        source_path = Path(path).expanduser().absolute()
        resolved_filename = _filename(filename or source_path.name)
        return cls._from_local_source(
            _PathImageSource(
                path=source_path,
                filename=resolved_filename,
                content_type=_content_type(resolved_filename, content_type),
                namespace=_namespace(namespace),
            ),
            alt_text=alt_text,
            on_click=on_click,
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray | memoryview,
        *,
        filename: str,
        content_type: str | None = None,
        namespace: str | None = None,
        alt_text: str | None = None,
        on_click: Action | OpenLink | None = None,
    ) -> Image:
        """Build an Image from an immutable snapshot of generated bytes."""
        snapshot = bytes(data)
        if not snapshot:
            raise ValueError("Local Card image bytes cannot be empty")
        resolved_filename = _filename(filename)
        return cls._from_local_source(
            _BytesImageSource(
                data=snapshot,
                filename=resolved_filename,
                content_type=_content_type(resolved_filename, content_type),
                namespace=_namespace(namespace),
            ),
            alt_text=alt_text,
            on_click=on_click,
        )

    @classmethod
    def _from_local_source(
        cls,
        source: _LocalImageSource,
        *,
        alt_text: str | None,
        on_click: Action | OpenLink | None,
    ) -> Image:
        image = cls.__new__(cls)
        object.__setattr__(image, "image_url", None)
        object.__setattr__(image, "alt_text", alt_text)
        object.__setattr__(image, "on_click", on_click)
        object.__setattr__(image, "_local_source", source)
        image._snapshot_action()
        return image

    def to_proto(self) -> ProtoImage:
        """Build the SDK Image proto."""
        if self.image_url is None:
            from chattice.exceptions import AssetPublishError

            raise AssetPublishError(
                "Local Card images must be resolved through the message resource "
                "clients before serialization"
            )
        kwargs: dict[str, Any] = {"image_url": self.image_url}
        if self.alt_text is not None:
            kwargs["alt_text"] = self.alt_text
        if self.on_click is not None:
            if isinstance(self.on_click, Action):
                kwargs["on_click"] = {"action": self.on_click.to_proto()}
            else:
                kwargs["on_click"] = {"open_link": self.on_click.to_proto()}
        return ProtoImage(**kwargs)


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
