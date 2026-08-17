"""Validation facade."""

from __future__ import annotations

from chattice.cards import TextInputType, Validation


def test_character_limit_only() -> None:
    proto = Validation(character_limit=50).to_proto()
    assert proto.character_limit == 50


def test_input_type() -> None:
    proto = Validation(input_type=TextInputType.EMAIL).to_proto()
    from google.apps.card_v1.types.card import Validation as ProtoValidation

    assert proto.input_type == ProtoValidation.InputType.EMAIL


def test_to_dict_shape() -> None:
    data = Validation(character_limit=50, input_type=TextInputType.TEXT).to_dict()
    assert data == {"characterLimit": 50, "inputType": "TEXT"}
