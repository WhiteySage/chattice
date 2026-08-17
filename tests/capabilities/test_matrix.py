"""Response/outbound capability model (post-review split)."""

from __future__ import annotations

import pytest

from chattice.auth import AuthMode
from chattice.capabilities import (
    PREVIEW_APP_COMMAND_TYPES,
    CapabilityNotSupported,
    OutboundCapabilities,
    OutboundCapability,
    PreviewCapabilities,
    PreviewFeature,
    ResponseCapabilities,
    ResponseCapability,
)
from chattice.events import (
    ActionEvent,
    AppHomeEvent,
    MessageEvent,
    WidgetUpdatedEvent,
)


def test_http_response_capabilities_base() -> None:
    capabilities = ResponseCapabilities.resolve(transport="http")
    assert ResponseCapability.SYNC_RESPONSE in capabilities
    # F08: DIALOGS is no longer granted unconditionally — only command
    # and REQUEST_DIALOG-action events may open a dialog.
    assert ResponseCapability.DIALOGS not in capabilities
    assert ResponseCapability.CARD_UPDATE_BOT not in capabilities


def test_pubsub_response_capabilities_are_empty() -> None:
    capabilities = ResponseCapabilities.resolve(transport="pubsub")
    assert ResponseCapability.SYNC_RESPONSE not in capabilities
    assert ResponseCapability.DIALOGS not in capabilities


def test_app_home_event_grants_app_home() -> None:
    capabilities = ResponseCapabilities.resolve(transport="http", event=AppHomeEvent())
    assert ResponseCapability.APP_HOME in capabilities


def test_bot_action_grants_card_update_bot() -> None:
    capabilities = ResponseCapabilities.resolve(
        transport="http", event=ActionEvent(name="x", sender_type="BOT")
    )
    assert ResponseCapability.CARD_UPDATE_BOT in capabilities
    assert ResponseCapability.CARD_UPDATE_USER not in capabilities


def test_human_action_grants_card_update_user() -> None:
    capabilities = ResponseCapabilities.resolve(
        transport="http", event=ActionEvent(name="x", sender_type="HUMAN")
    )
    assert ResponseCapability.CARD_UPDATE_USER in capabilities
    assert ResponseCapability.CARD_UPDATE_BOT not in capabilities


def test_matched_url_message_grants_card_update_user() -> None:
    capabilities = ResponseCapabilities.resolve(
        transport="http",
        event=MessageEvent(text="u", matched_url="https://example.com/x"),
    )
    assert ResponseCapability.CARD_UPDATE_USER in capabilities


def test_widget_updated_grants_update_widget() -> None:
    capabilities = ResponseCapabilities.resolve(
        transport="http", event=WidgetUpdatedEvent(function_name="f")
    )
    assert ResponseCapability.UPDATE_WIDGET in capabilities


def test_unknown_transport_rejected() -> None:
    with pytest.raises(ValueError, match="transport"):
        ResponseCapabilities.resolve(transport="sms")


def test_response_require_satisfied() -> None:
    ResponseCapabilities.resolve(transport="http").require(
        ResponseCapability.SYNC_RESPONSE
    )


def test_response_require_raises_with_actionable_message() -> None:
    with pytest.raises(CapabilityNotSupported, match="SYNC_RESPONSE"):
        ResponseCapabilities.resolve(transport="pubsub").require(
            ResponseCapability.SYNC_RESPONSE
        )


def test_app_outbound_capabilities() -> None:
    capabilities = OutboundCapabilities.resolve(AuthMode.APP)
    assert OutboundCapability.MESSAGE_CREATE in capabilities
    assert OutboundCapability.MESSAGE_UPDATE in capabilities
    assert OutboundCapability.USER_IMPERSONATION not in capabilities


def test_user_outbound_capabilities() -> None:
    capabilities = OutboundCapabilities.resolve(AuthMode.USER)
    assert OutboundCapability.MESSAGE_CREATE in capabilities
    assert OutboundCapability.USER_IMPERSONATION in capabilities


def test_none_outbound_capabilities_are_empty() -> None:
    capabilities = OutboundCapabilities.resolve(AuthMode.NONE)
    assert OutboundCapability.MESSAGE_CREATE not in capabilities
    assert OutboundCapability.USER_IMPERSONATION not in capabilities


def test_outbound_require_raises() -> None:
    with pytest.raises(CapabilityNotSupported, match="MESSAGE_CREATE"):
        OutboundCapabilities.resolve(AuthMode.NONE).require(
            OutboundCapability.MESSAGE_CREATE
        )


def test_preview_app_command_types_are_documented() -> None:
    assert "MESSAGE_ACTION" in PREVIEW_APP_COMMAND_TYPES
    assert PreviewFeature.MESSAGE_ACTION.name == "MESSAGE_ACTION"


def test_preview_capabilities_are_explicit_and_fail_closed() -> None:
    disabled = PreviewCapabilities()
    assert PreviewFeature.MESSAGE_ACTION not in disabled
    with pytest.raises(CapabilityNotSupported, match="Developer Preview"):
        disabled.require(PreviewFeature.MESSAGE_ACTION)

    enabled = PreviewCapabilities({PreviewFeature.MESSAGE_ACTION})
    enabled.require(PreviewFeature.MESSAGE_ACTION)
