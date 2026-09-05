"""HTTP transport exception hierarchy."""

from __future__ import annotations

import pytest

from chattice.transports.http.errors import (
    DoubleResponseError,
    HTTPInteractionError,
    VerificationError,
)


def test_hierarchy() -> None:
    assert issubclass(VerificationError, HTTPInteractionError)
    assert issubclass(DoubleResponseError, HTTPInteractionError)
    assert issubclass(HTTPInteractionError, ValueError)


def test_messages_carry_through() -> None:
    with pytest.raises(VerificationError, match="bad token"):
        raise VerificationError("bad token")
