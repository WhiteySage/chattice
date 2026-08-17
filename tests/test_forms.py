"""Typed form decoding (B4)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import (
    ActionEvent,
    DateInput,
    FormInputs,
    FormValue,
    StringInput,
    TimeInput,
)
from chattice.forms import FormDecodeError, FormModel


@dataclass
class ContactForm(FormModel):
    name: StringInput
    birthday: DateInput | None = None
    reminder_time: TimeInput | None = None


def _inputs(**values: FormValue) -> FormInputs:
    return FormInputs(data=values)


def test_decodes_present_typed_values() -> None:
    form = ContactForm.from_form_inputs(
        _inputs(
            name=StringInput(values=("Иван",)),
            birthday=DateInput(ms_since_epoch=1710000000000),
            reminder_time=TimeInput(hours=9, minutes=30),
        )
    )
    assert form.name.values == ("Иван",)
    assert form.birthday is not None and form.birthday.ms_since_epoch == 1710000000000
    assert form.reminder_time is not None and form.reminder_time.hours == 9


def test_missing_optional_fields_fall_back_to_defaults() -> None:
    form = ContactForm.from_form_inputs(_inputs(name=StringInput(values=("Иван",))))
    assert form.birthday is None
    assert form.reminder_time is None


def test_missing_required_field_raises() -> None:
    with pytest.raises(FormDecodeError, match="name"):
        ContactForm.from_form_inputs(_inputs())


def test_wrong_input_kind_raises() -> None:
    with pytest.raises(FormDecodeError, match="expected StringInput"):
        ContactForm.from_form_inputs(_inputs(name=DateInput(ms_since_epoch=1)))


def test_unsupported_field_type_rejected() -> None:
    @dataclass
    class Bad(FormModel):
        value: dict[str, str]

    with pytest.raises(TypeError, match="StringInput"):
        Bad.from_form_inputs(_inputs())


def _submit(name: str, birthday_ms: int | None = None) -> ActionEvent:
    form_inputs: dict[str, object] = {"name": {"stringInputs": {"value": [name]}}}
    if birthday_ms is not None:
        form_inputs["birthday"] = {"dateInput": {"msSinceEpoch": birthday_ms}}
    payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {"invokedFunction": "contact.submit", "formInputs": form_inputs},
    }
    from typing import cast

    return cast(ActionEvent, parse_interaction(payload))


async def test_filter_injects_decoded_form() -> None:
    router = Router()
    seen: list[ContactForm] = []

    @router.dialog_submit(ContactForm.filter())
    async def submit(event: ActionEvent, form: ContactForm) -> str:
        seen.append(form)
        return form.name.values[0]

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    outcome = await dispatcher.feed_update(_submit("Иван"))
    assert outcome == "Иван"
    assert seen and seen[0].name.values == ("Иван",)


async def test_filter_does_not_match_on_malformed_inputs() -> None:
    router = Router()
    matched = False

    @router.dialog_submit(ContactForm.filter())
    async def submit(event: ActionEvent, form: ContactForm) -> str:
        nonlocal matched
        matched = True
        return "x"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    # no "name" input -> decode error -> filter False
    payload = {
        "type": "CARD_CLICKED",
        "isDialogEvent": True,
        "dialogEventType": "SUBMIT_DIALOG",
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
        "common": {"invokedFunction": "contact.submit", "formInputs": {}},
    }
    result = await dispatcher.feed_update(parse_interaction(payload))
    assert result is None
    assert matched is False
