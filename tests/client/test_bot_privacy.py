"""F01 regression: outbound privacy and preview gates fail closed.

Every rejected request must make ZERO transport calls — privacy intent
can never silently become public, and validation happens before lazy
client creation.
"""

from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported
from chattice.cards import (
    AccessoryWidget,
    Button,
    ButtonList,
    Card,
    CardHeader,
    Section,
    TextParagraph,
)
from chattice.client import Bot, ChatAPIError
from chattice.events import UserRef

from ._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


def _bot(
    transport: FakeChatTransport, *, auth_mode: AuthMode | None = AuthMode.APP
) -> Bot:
    return Bot(credentials=_creds(), auth_mode=auth_mode, transport=transport)


def _card() -> Card:
    return Card(
        header=CardHeader(title="T"),
        sections=[Section(widgets=[TextParagraph("hi")])],
    )


def _accessory() -> list[AccessoryWidget]:
    return [
        AccessoryWidget(button_list=ButtonList(buttons=[Button("Go", action="nav.go")]))
    ]


@pytest.mark.parametrize(
    "private_to",
    ["", "   ", UserRef(name=None), UserRef(name=""), UserRef(name="  ")],
)
async def test_private_to_fails_closed(private_to: object) -> None:
    transport = FakeChatTransport()
    with pytest.raises(ChatAPIError):
        await _bot(transport).send_message(
            "spaces/AAA",
            text="secret",
            private_to=private_to,  # type: ignore[arg-type]
        )
    assert transport.requests == []


async def test_private_to_requires_app_auth() -> None:
    transport = FakeChatTransport()
    with pytest.raises(CapabilityNotSupported):
        await _bot(transport, auth_mode=AuthMode.USER).send_message(
            "spaces/AAA", text="secret", private_to="users/9"
        )
    assert transport.requests == []


async def test_private_to_unknown_auth_mode_fails_closed() -> None:
    """Unclassifiable credentials (mode None) must also reject, not pass."""
    transport = FakeChatTransport()
    with pytest.raises(CapabilityNotSupported):
        await _bot(transport, auth_mode=None).send_message(
            "spaces/AAA", text="secret", private_to="users/9"
        )
    assert transport.requests == []


async def test_private_to_with_accessory_widgets_rejected() -> None:
    transport = FakeChatTransport()
    with pytest.raises(ChatAPIError):
        await _bot(transport).send_message(
            "spaces/AAA",
            text="secret",
            private_to="users/9",
            accessory_widgets=_accessory(),
        )
    assert transport.requests == []


@pytest.mark.parametrize("viewer,expected", [("9", "users/9"), ("users/9", "users/9")])
async def test_private_to_canonical_serialization(viewer: str, expected: str) -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message("spaces/AAA", text="secret", private_to=viewer)
    request = transport.requests[-1]
    assert request.message.private_message_viewer.name == expected


@pytest.mark.parametrize("viewer", ["users/9/x", "9/x", "spaces/9"])
async def test_private_to_malformed_rejected(viewer: str) -> None:
    transport = FakeChatTransport()
    with pytest.raises(ChatAPIError):
        await _bot(transport).send_message(
            "spaces/AAA", text="secret", private_to=viewer
        )
    assert transport.requests == []


async def test_notify_invalid_value_rejected() -> None:
    transport = FakeChatTransport()
    with pytest.raises(ChatAPIError):
        await _bot(transport).send_message("spaces/AAA", text="x", notify="loud")
    assert transport.requests == []


async def test_notify_requires_app_auth() -> None:
    transport = FakeChatTransport()
    with pytest.raises(CapabilityNotSupported):
        await _bot(transport, auth_mode=AuthMode.USER).send_message(
            "spaces/AAA", text="x", notify="silent"
        )
    assert transport.requests == []


@pytest.mark.parametrize("notify", ["force", "silent"])
async def test_notify_valid_values_serialized(notify: str) -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message("spaces/AAA", text="x", notify=notify)
    options = transport.requests[-1].create_message_notification_options
    expected = (
        "NOTIFICATION_TYPE_FORCE_NOTIFY"
        if notify == "force"
        else "NOTIFICATION_TYPE_SILENT"
    )
    assert options.notification_type.name == expected


async def test_user_auth_card_rejected_without_preview_opt_in() -> None:
    transport = FakeChatTransport()
    with pytest.raises(CapabilityNotSupported):
        await _bot(transport, auth_mode=AuthMode.USER).send_message(
            "spaces/AAA", card=_card()
        )
    assert transport.requests == []


async def test_user_auth_text_allowed() -> None:
    """Only CARDS are Developer Preview under user auth; text stays valid."""
    transport = FakeChatTransport()
    await _bot(transport, auth_mode=AuthMode.USER).send_message(
        "spaces/AAA", text="plain"
    )
    assert transport.requests[-1].message.text == "plain"


async def test_app_auth_card_allowed() -> None:
    transport = FakeChatTransport()
    await _bot(transport).send_message("spaces/AAA", card=_card())
    assert len(transport.requests[-1].message.cards_v2) == 1
