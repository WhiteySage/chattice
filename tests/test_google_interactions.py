"""Documented Google Chat interaction adapter and dispatcher integration tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from chattice import Dispatcher, F, Router
from chattice.adapters.google_chat import (
    ConflictingEnvelopeError,
    GoogleInteractionAdapter,
    InvalidInteractionPayload,
    UnsupportedEnvelopeError,
    parse_interaction,
)
from chattice.events import (
    ActionEvent,
    ActionSource,
    AddedToSpaceEvent,
    AppHomeEvent,
    CommandEvent,
    CommandKind,
    DateInput,
    DateTimeInput,
    DialogEventType,
    Event,
    FormSubmitEvent,
    MessageEvent,
    RemovedFromSpaceEvent,
    StringInput,
    TimeInput,
    UnknownEvent,
    UnknownFormInput,
    WidgetUpdatedEvent,
)

FIXTURES = Path(__file__).parent / "fixtures/google_chat/interactions"


def load_fixture(name: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((FIXTURES / name).read_text()))


def test_message_normalization_and_deep_raw_snapshot() -> None:
    payload = load_fixture("message.json")
    event = parse_interaction(payload)

    assert isinstance(event, MessageEvent)
    assert event.text == "ping"
    assert event.event_time == datetime(2026, 8, 13, 12, 34, 56, 123456, tzinfo=UTC)
    assert event.actor and event.actor.name == "users/123"
    assert event.space and event.space.name == "spaces/AAA"
    assert event.thread and event.thread.name == "spaces/AAA/threads/THR"
    assert event.message and event.message.name == "spaces/AAA/messages/MSG"
    assert cast(dict[str, object], event.raw)["extraFutureField"] == {"kept": True}

    cast(dict[str, Any], payload["message"])["text"] = "mutated"
    assert (
        cast(dict[str, Any], cast(dict[str, Any], event.raw)["message"])["text"]
        == "ping"
    )


def test_adapter_object_is_a_stateless_facade() -> None:
    event = GoogleInteractionAdapter().parse(load_fixture("message.json"))
    assert isinstance(event, MessageEvent)


def test_card_action_common_data_locale_timezone_and_legacy_agreement() -> None:
    event = parse_interaction(load_fixture("card_clicked.json"))

    assert isinstance(event, ActionEvent)
    assert event.name == event.function_name == "deploy.confirm"
    assert event.parameters == {"environment": "prod"}
    assert event.locale == "en-US"
    assert event.timezone and event.timezone.id == "America/Los_Angeles"
    assert event.timezone.offset_ms == -25200000
    with pytest.raises(TypeError):
        cast(Any, event.parameters)["environment"] = "dev"


def test_form_inputs_preserve_every_documented_variant() -> None:
    event = parse_interaction(load_fixture("card_clicked_form.json"))
    assert isinstance(event, ActionEvent)

    name = event.form_inputs["contactName"]
    selections = event.form_inputs["contactTypes"]
    birthdate = event.form_inputs["contactBirthdate"]
    appointment = event.form_inputs["appointment"]
    reminder = event.form_inputs["reminder"]
    assert isinstance(name, StringInput) and name.values == ("Kai O",)
    assert isinstance(selections, StringInput) and selections.values == (
        "Personal",
        "Work",
    )
    assert isinstance(birthdate, DateInput)
    assert birthdate.ms_since_epoch == 1000425600000
    assert isinstance(appointment, DateTimeInput)
    assert appointment.ms_since_epoch == 1786638600000
    assert appointment.has_date is appointment.has_time is True
    assert isinstance(reminder, TimeInput)
    assert (reminder.hours, reminder.minutes) == (9, 30)


def test_unknown_form_variant_is_representable() -> None:
    payload: Mapping[str, object] = {
        "type": "CARD_CLICKED",
        "common": {
            "invokedFunction": "future.input",
            "formInputs": {"future": {"colorInput": {"value": "blue"}}},
        },
    }
    event = parse_interaction(payload)
    assert isinstance(event, ActionEvent)
    value = event.form_inputs["future"]
    assert isinstance(value, UnknownFormInput)
    assert value.kind == "colorInput"


@pytest.mark.parametrize(
    ("fixture", "dialog_type"),
    [
        ("card_clicked_request_dialog.json", DialogEventType.REQUEST_DIALOG),
        ("card_clicked_submit_dialog.json", DialogEventType.SUBMIT_DIALOG),
        ("card_clicked_cancel_dialog.json", DialogEventType.CANCEL_DIALOG),
    ],
)
def test_dialog_metadata(fixture: str, dialog_type: DialogEventType) -> None:
    event = parse_interaction(load_fixture(fixture))
    assert isinstance(event, ActionEvent)
    assert event.dialog and event.dialog.type is dialog_type
    assert event.dialog.is_dialog_event is True
    assert event.source is ActionSource.DIALOG


def test_unknown_dialog_value_is_preserved() -> None:
    event = parse_interaction(
        {
            "type": "CARD_CLICKED",
            "isDialogEvent": True,
            "dialogEventType": "FUTURE_DIALOG_STATE",
            "common": {"invokedFunction": "future.dialog"},
        }
    )
    assert isinstance(event, ActionEvent)
    assert event.dialog and event.dialog.type == "FUTURE_DIALOG_STATE"


def test_command_metadata_has_no_fabricated_name() -> None:
    event = parse_interaction(load_fixture("app_command.json"))
    assert isinstance(event, CommandEvent)
    assert event.command_id == 42
    assert event.command_type == "QUICK_COMMAND"
    assert event.kind is CommandKind.QUICK_COMMAND
    assert event.source_kind == "QUICK_COMMAND"
    assert event.message_text == "/deploy prod"
    assert not hasattr(event, "name")


def test_slash_command_arrives_as_message_and_routes_to_command() -> None:
    """Official command guide: slash commands are MESSAGE events with
    message.slashCommand + argumentText — they produce CommandEvent with
    source kind SLASH_COMMAND."""
    event = parse_interaction(load_fixture("slash_command.json"))
    assert isinstance(event, CommandEvent)
    assert event.command_id == 42
    assert event.command_type is None
    assert event.kind is CommandKind.SLASH_COMMAND
    assert event.source_kind == "SLASH_COMMAND"
    assert event.message_text == "deploy prod"  # argumentText wins over text


def test_slash_command_without_command_id_is_rejected() -> None:
    with pytest.raises(InvalidInteractionPayload, match="commandId"):
        parse_interaction(
            {
                "type": "MESSAGE",
                "message": {"slashCommand": {}},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        )


def test_slash_command_non_integer_command_id_is_rejected() -> None:
    with pytest.raises(InvalidInteractionPayload, match="int64"):
        parse_interaction(
            {
                "type": "MESSAGE",
                "message": {"slashCommand": {"commandId": "abc"}},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        )


def test_message_action_preserves_preview_kind_and_target_message() -> None:
    """MESSAGE_ACTION is a Developer Preview APP_COMMAND type — accepted,
    marked by source kind, not advertised as stable."""
    event = parse_interaction(load_fixture("message_action.json"))
    assert isinstance(event, CommandEvent)
    assert event.source_kind == "MESSAGE_ACTION"
    assert event.kind is CommandKind.MESSAGE_ACTION
    assert event.command_id == 7
    assert event.target_message is not None
    assert event.target_message.name == "spaces/AAA/messages/TARGET"


def test_message_event_exposes_matched_url_and_sender_type() -> None:
    event = parse_interaction(load_fixture("message_matched_url.json"))
    assert isinstance(event, MessageEvent)
    assert event.matched_url == "https://example.com/ticket/42"
    assert event.sender_type == "HUMAN"


def test_action_event_exposes_sender_type() -> None:
    event = parse_interaction(load_fixture("card_clicked_human_message.json"))
    assert isinstance(event, ActionEvent)
    assert event.name == "deploy.confirm"
    assert event.sender_type == "HUMAN"
    assert event.source is ActionSource.MESSAGE


def test_app_home_action_has_typed_source() -> None:
    event = parse_interaction(load_fixture("app_home_card_clicked.json"))
    assert isinstance(event, ActionEvent)
    assert event.source is ActionSource.HOME


def test_direct_action_without_source_evidence_stays_unknown() -> None:
    event = parse_interaction(load_fixture("card_clicked.json"))
    assert isinstance(event, ActionEvent)
    assert event.source is None


def test_app_command_slash_wire_mismatch_is_not_promoted() -> None:
    event = parse_interaction(
        {
            "type": "APP_COMMAND",
            "appCommandMetadata": {
                "appCommandId": 42,
                "appCommandType": "SLASH_COMMAND",
            },
        }
    )
    assert isinstance(event, CommandEvent)
    assert event.source_kind == "SLASH_COMMAND"
    assert event.kind is None


def test_lifecycle_widget_and_wrapped_app_home_events() -> None:
    added = parse_interaction(load_fixture("added_to_space.json"))
    removed = parse_interaction(load_fixture("removed_from_space.json"))
    widget = parse_interaction(load_fixture("widget_updated.json"))
    home = parse_interaction(load_fixture("app_home.json"))

    assert isinstance(added, AddedToSpaceEvent)
    assert isinstance(removed, RemovedFromSpaceEvent)
    assert added.actor and added.space
    assert removed.actor and removed.space
    assert isinstance(widget, WidgetUpdatedEvent)
    assert widget.function_name == "search.contacts"
    assert widget.parameters["autocomplete_widget_query"] == "Kai"
    assert isinstance(home, AppHomeEvent)
    assert home.actor and home.actor.name == "users/123"
    assert home.space and home.space.name == "spaces/DM"
    assert cast(dict[str, object], home.raw).get("chat") is not None


def test_wrapped_submit_form_uses_outer_common_event_object() -> None:
    event = parse_interaction(load_fixture("submit_form.json"))
    assert isinstance(event, FormSubmitEvent)
    assert event.function_name == "update_app_home"
    assert event.parameters == {"section": "profile"}
    display_name = event.form_inputs["displayName"]
    assert isinstance(display_name, StringInput)
    assert display_name.values == ("Ada",)


def test_same_type_direct_and_wrapped_data_can_agree() -> None:
    event = parse_interaction(
        {
            "type": "APP_HOME",
            "chat": {
                "type": "APP_HOME",
                "user": {"name": "users/123"},
                "space": {"name": "spaces/DM"},
            },
        }
    )
    assert isinstance(event, AppHomeEvent)


def test_unknown_event_is_distinct_from_malformed_payload() -> None:
    event = parse_interaction(load_fixture("unknown_event.json"))
    assert isinstance(event, UnknownEvent)
    assert event.original_type == "SOME_FUTURE_GOOGLE_EVENT"
    assert event.event_time and event.event_time.tzinfo is not None

    with pytest.raises(UnsupportedEnvelopeError):
        parse_interaction(load_fixture("malformed_missing_type.json"))
    with pytest.raises(InvalidInteractionPayload):
        parse_interaction(load_fixture("malformed_type.json"))
    with pytest.raises(InvalidInteractionPayload, match="timezone"):
        parse_interaction(load_fixture("malformed_timestamp.json"))
    with pytest.raises(ConflictingEnvelopeError, match="types conflict"):
        parse_interaction(load_fixture("malformed_conflict.json"))
    with pytest.raises(InvalidInteractionPayload, match="UNSPECIFIED"):
        parse_interaction({"type": "UNSPECIFIED"})
    with pytest.raises(InvalidInteractionPayload, match="message"):
        parse_interaction({"type": "MESSAGE"})
    with pytest.raises(InvalidInteractionPayload, match="dialogEventType"):
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "isDialogEvent": True,
                "common": {"invokedFunction": "dialog"},
            }
        )
    with pytest.raises(InvalidInteractionPayload, match="appCommandMetadata"):
        parse_interaction({"type": "APP_COMMAND"})


def test_conflicting_common_and_action_metadata_fails() -> None:
    with pytest.raises(ConflictingEnvelopeError, match="invokedFunction"):
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "common": {"invokedFunction": "modern"},
                "action": {"actionMethodName": "legacy"},
            }
        )
    with pytest.raises(ConflictingEnvelopeError, match="commonEventObject"):
        parse_interaction(
            {
                "type": "CARD_CLICKED",
                "common": {"invokedFunction": "direct"},
                "commonEventObject": {"invokedFunction": "outer"},
            }
        )


@pytest.mark.parametrize(
    ("fixture", "observer", "event_class"),
    [
        ("message.json", "message", MessageEvent),
        ("added_to_space.json", "added_to_space", AddedToSpaceEvent),
        ("removed_from_space.json", "removed_from_space", RemovedFromSpaceEvent),
        ("card_clicked.json", "action", ActionEvent),
        ("widget_updated.json", "widget_updated", WidgetUpdatedEvent),
        ("app_command.json", "command", CommandEvent),
        ("app_home.json", "app_home", AppHomeEvent),
        ("submit_form.json", "form_submit", FormSubmitEvent),
    ],
)
async def test_every_supported_fixture_dispatches_to_typed_observer(
    fixture: str, observer: str, event_class: type[Event]
) -> None:
    router = Router()

    async def typed_handler(event: Event) -> str:
        assert isinstance(event, event_class)
        return event_class.__name__

    getattr(router, observer).register(typed_handler)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    event = parse_interaction(load_fixture(fixture))
    assert await dispatcher.feed_update(event) == event_class.__name__


async def test_documented_developer_experience_needs_no_raw_traversal() -> None:
    router = Router()

    @router.message(F.text == "ping")
    async def ping(message: MessageEvent) -> str:
        return "pong"

    @router.action("deploy.confirm")
    async def confirm(action: ActionEvent) -> str:
        environment = action.parameters["environment"]
        assert isinstance(environment, str)
        return environment

    @router.command()
    async def command(event: CommandEvent) -> int:
        return event.command_id

    @router.app_home()
    async def home(event: AppHomeEvent) -> str:
        return "home"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    assert (
        await dispatcher.feed_update(parse_interaction(load_fixture("message.json")))
        == "pong"
    )
    assert (
        await dispatcher.feed_update(
            parse_interaction(load_fixture("card_clicked.json"))
        )
        == "prod"
    )
    assert (
        await dispatcher.feed_update(
            parse_interaction(load_fixture("app_command.json"))
        )
        == 42
    )
    assert (
        await dispatcher.feed_update(parse_interaction(load_fixture("app_home.json")))
        == "home"
    )
