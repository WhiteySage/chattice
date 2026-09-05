"""Typed form decoding: opt-in schemas above the existing typed FormInputs.

Google's ``common.formInputs`` values are ALREADY typed by the adapter
(StringInput / DateInput / DateTimeInput / TimeInput / UnknownFormInput).
``FormModel`` adds an opt-in dataclass schema that maps widget names onto
those typed values — no string flattening, no mandatory pydantic domain
model, and no automatic translation of decode errors into dialog errors
(Google's error response rules depend on the surface; the application
decides how to answer).

Usage:

    @dataclass
    class ContactForm(FormModel):
        name: StringInput
        birthday: DateInput | None = None

    @router.dialog_submit(ContactForm.filter())
    async def submit(event: ActionEvent, form: ContactForm): ...

On a match the decoded instance is injected under the name ``form``.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from typing import Any, Self, cast, get_type_hints

from chattice.events import (
    ActionEvent,
    DateInput,
    DateTimeInput,
    Event,
    FormInputs,
    FormSubmitEvent,
    StringInput,
    TimeInput,
    UnknownFormInput,
)
from chattice.filters import FilterValue

_logger = logging.getLogger("chattice.forms")

__all__ = ["FormDecodeError", "FormFilter", "FormModel"]

_SUPPORTED = (StringInput, DateInput, DateTimeInput, TimeInput, UnknownFormInput)


class FormDecodeError(ValueError):
    """Form inputs cannot be decoded into the typed model."""


def _unwrap_optional(target: type[object]) -> type[object]:
    import types
    from typing import Union, get_args, get_origin

    origin = get_origin(target)
    if origin in (Union, types.UnionType):
        args = get_args(target)
        if len(args) == 2 and type(None) in args:
            # pick the NON-None member regardless of union order
            return cast(type[object], args[0] if args[1] is type(None) else args[1])
    return target


def _required_field_names(model: type[FormModel]) -> set[str]:
    required: set[str] = set()
    for field in dataclasses.fields(cast(Any, model)):
        if (
            field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        ):
            required.add(field.name)
    return required


class FormModel:
    """Base class for typed form-input models (dataclass subclasses)."""

    @classmethod
    def _fields(cls) -> dict[str, type[object]]:
        if not hasattr(cls, "__dataclass_fields__"):
            raise TypeError(f"{cls.__name__} must be a dataclass FormModel")
        hints = get_type_hints(cls)
        return {
            field.name: hints[field.name]
            for field in dataclasses.fields(cast(Any, cls))
            if field.name in hints
        }

    @classmethod
    def from_form_inputs(cls, inputs: FormInputs) -> Self:
        """Decode typed form inputs into an instance.

        Missing optional fields fall back to their dataclass defaults;
        missing required fields raise FormDecodeError. A present value of
        the wrong input kind (e.g. DateInput where StringInput was
        declared) raises FormDecodeError.
        """
        fields = cls._fields()
        values: dict[str, object] = {}
        for name, target in fields.items():
            target = _unwrap_optional(target)
            if target not in _SUPPORTED:
                raise TypeError(
                    f"FormModel field {name!r} must be one of "
                    f"{[t.__name__ for t in _SUPPORTED]}"
                )
            if name not in inputs:
                if name in _required_field_names(cls):
                    raise FormDecodeError(
                        f"missing required form input {name!r} for {cls.__name__}"
                    )
                continue  # optional: dataclass default applies
            value = inputs[name]
            if not isinstance(value, target):
                raise FormDecodeError(
                    f"form input {name!r} is {type(value).__name__}, "
                    f"expected {target.__name__}"
                )
            values[name] = value
        return cls(**values)

    @classmethod
    def filter(cls) -> FormFilter:
        """An async filter matching when form inputs decode into this model.

        On a match the decoded instance is injected into the handler
        context under the name ``form``.
        """
        return FormFilter(cls)


class FormFilter:
    """Decode-based filter: returns ``{"form": instance}`` or False.

    Accepts the full event union that owns typed ``form_inputs`` —
    dialog ``ActionEvent`` AND App Home ``FormSubmitEvent`` — so the
    advertised form logic is reusable on App Home submits.
    """

    def __init__(self, model: type[FormModel]) -> None:
        self.model = model

    async def __call__(
        self, event: Event, context: Mapping[str, object]
    ) -> FilterValue:
        if not isinstance(event, (ActionEvent, FormSubmitEvent)):
            return False
        try:
            instance = self.model.from_form_inputs(event.form_inputs)
        except FormDecodeError as error:
            # A filter mismatch is silent by contract, but a decode failure
            # of an explicitly registered typed form is worth a debug line:
            # new users otherwise search for hours why a button "does nothing".
            _logger.debug(
                "form decode failed for %s: %s",
                self.model.__name__,
                error,
            )
            return False
        return {"form": instance}
