"""IncomingRequest value object."""

from __future__ import annotations

import pytest

from chattice.adapters.google_chat.exceptions import InvalidInteractionPayload
from chattice.transports.http import IncomingRequest


def _request(body: bytes = b"") -> IncomingRequest:
    return IncomingRequest(
        method="POST",
        path="/chat",
        body=body,
        headers={"Content-Type": "application/json"},
    )


def test_header_lookup_is_case_insensitive() -> None:
    request = IncomingRequest(
        method="POST", path="/", headers={"Authorization": "Bearer x"}
    )
    assert request.header("authorization") == "Bearer x"
    assert request.header("AUTHORIZATION") == "Bearer x"
    assert request.header("X-Unknown") is None


def test_json_decodes_mapping() -> None:
    request = _request(b'{"type": "MESSAGE"}')
    assert request.json() == {"type": "MESSAGE"}


def test_json_rejects_invalid_body() -> None:
    with pytest.raises(InvalidInteractionPayload):
        _request(b"not json").json()


def test_json_rejects_non_mapping_root() -> None:
    with pytest.raises(InvalidInteractionPayload):
        _request(b"[1, 2]").json()


def test_json_rejects_empty_body() -> None:
    with pytest.raises(InvalidInteractionPayload):
        _request().json()
