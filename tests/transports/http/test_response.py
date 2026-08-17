"""Synchronous response state."""

from __future__ import annotations

import pytest

from chattice.transports.http import (
    DoubleResponseError,
    InteractionResponse,
    ResponseState,
)


def test_starts_not_responded() -> None:
    response = InteractionResponse()
    assert response.state is ResponseState.NOT_RESPONDED
    assert response.payload is None


def test_respond_sets_payload_once() -> None:
    response = InteractionResponse()
    response.respond({"text": "hi"})
    assert response.state is ResponseState.RESPONDED
    assert response.payload == {"text": "hi"}


def test_second_respond_raises() -> None:
    response = InteractionResponse()
    response.respond("first")
    with pytest.raises(DoubleResponseError):
        response.respond("second")
    assert response.payload == "first"


def test_none_payload_is_a_valid_response() -> None:
    response = InteractionResponse()
    response.respond(None)
    assert response.state is ResponseState.RESPONDED
