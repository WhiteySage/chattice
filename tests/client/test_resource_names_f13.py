"""F13 regression: one resource-name policy for space targets.

Bare IDs canonicalize to spaces/{id} before any transport work;
malformed values fail locally with zero transport calls.
"""

from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.client import Bot, ChatAPIError
from chattice.events import SpaceRef

from ._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _bot(transport: FakeChatTransport) -> Bot:
    return Bot(credentials=_creds(), auth_mode=AuthMode.APP, transport=transport)


@pytest.mark.parametrize(
    "space,expected",
    [
        ("AAA", "spaces/AAA"),
        ("spaces/AAA", "spaces/AAA"),
        (SpaceRef(name="BBB"), "spaces/BBB"),
        (SpaceRef(name="spaces/CCC"), "spaces/CCC"),
    ],
)
async def test_space_canonicalization(space: object, expected: str) -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message(space, text="x")  # type: ignore[arg-type]
    assert transport.requests[-1].parent == expected


@pytest.mark.parametrize(
    "space",
    ["", "   ", "AAA/BBB", "users/9", "spaces/AAA/x", SpaceRef(name=None)],
)
async def test_malformed_space_rejected_locally(space: object) -> None:
    transport = FakeChatTransport()
    with pytest.raises(ChatAPIError):
        await _bot(transport).send_message(space, text="x")  # type: ignore[arg-type]
    assert transport.requests == []  # zero transport calls on invalid input
