"""Pure mapping from validated Google interaction data to domain events."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TypedDict

from pydantic import ValidationError

from chattice.events import (
    ActionEvent,
    ActionSource,
    AddedToSpaceEvent,
    AppHomeEvent,
    CommandEvent,
    CommandKind,
    DialogEventType,
    DialogMetadata,
    Event,
    FormInputs,
    FormSubmitEvent,
    MessageEvent,
    MessageRef,
    RemovedFromSpaceEvent,
    SpaceRef,
    ThreadRef,
    TimeZone,
    UnknownEvent,
    UserRef,
    WidgetUpdatedEvent,
)

from .envelope import normalize_envelope
from .exceptions import ConflictingEnvelopeError, InvalidInteractionPayload
from .inputs import parse_form_inputs
from .models import InteractionModel, SpaceModel, ThreadModel, UserModel

_KNOWN_TYPES = {
    "MESSAGE",
    "ADDED_TO_SPACE",
    "REMOVED_FROM_SPACE",
    "CARD_CLICKED",
    "WIDGET_UPDATED",
    "APP_COMMAND",
    "APP_HOME",
    "SUBMIT_FORM",
}


class _EventKwargs(TypedDict):
    raw: object
    event_time: datetime | None
    actor: UserRef | None
    space: SpaceRef | None
    thread: ThreadRef | None
    dialog: DialogMetadata | None
    locale: str | None
    timezone: TimeZone | None


def parse_interaction(payload: Mapping[str, object]) -> Event:
    """Parse a documented Google Chat interaction mapping into a domain event."""
    envelope = normalize_envelope(payload)
    try:
        model = InteractionModel.model_validate(envelope.event)
    except ValidationError as error:
        raise InvalidInteractionPayload(
            f"Invalid Google Chat interaction payload: {error}"
        ) from error

    if model.type in {"UNSPECIFIED", "TYPE_UNSPECIFIED"}:
        raise InvalidInteractionPayload("UNSPECIFIED is not an interaction event")

    event_time = _timestamp(model.event_time)
    actor = _user(model.user or (model.message.sender if model.message else None))
    space = _space(model.space or (model.message.space if model.message else None))
    thread = _thread(
        model.thread or (model.message.thread if model.message else None),
        space=space,
    )
    dialog = _dialog(model.is_dialog_event, model.dialog_event_type)
    common = model.common
    locale = common.user_locale if common else None
    timezone = (
        TimeZone(id=common.time_zone.id, offset_ms=common.time_zone.offset)
        if common and common.time_zone
        else None
    )
    base: _EventKwargs = {
        "raw": envelope.raw,
        "event_time": event_time,
        "actor": actor,
        "space": space,
        "thread": thread,
        "dialog": dialog,
        "locale": locale,
        "timezone": timezone,
    }

    if model.type not in _KNOWN_TYPES:
        return UnknownEvent(original_type=model.type, **base)
    if model.type == "MESSAGE":
        if model.message is None:
            raise InvalidInteractionPayload("MESSAGE requires a message object")
        # Slash commands arrive as MESSAGE events with message.slashCommand
        # (documented command guide): route them to the SAME CommandEvent
        # family as APP_COMMAND quick commands.
        if model.message.slash_command is not None:
            return _slash_command_event(model, base)
        if model.message.text is None:
            raise InvalidInteractionPayload("MESSAGE requires message.text")
        return MessageEvent(
            text=model.message.text,
            message=MessageRef(name=model.message.name),
            matched_url=(
                model.message.matched_url.url if model.message.matched_url else None
            ),
            sender_type=model.message.sender.type if model.message.sender else None,
            argument_text=model.message.argument_text,
            **base,
        )
    if model.type == "ADDED_TO_SPACE":
        _require_actor_space(model.type, actor, space)
        return AddedToSpaceEvent(**base)
    if model.type == "REMOVED_FROM_SPACE":
        _require_actor_space(model.type, actor, space)
        return RemovedFromSpaceEvent(**base)
    if model.type == "APP_HOME":
        _require_actor_space(model.type, actor, space)
        return AppHomeEvent(**base)

    parameters, form_inputs, function_name = _common_action(model)
    if model.type == "CARD_CLICKED":
        if not function_name:
            raise InvalidInteractionPayload(
                "CARD_CLICKED requires common.invokedFunction or "
                "action.actionMethodName"
            )
        return ActionEvent(
            name=function_name,
            parameters=parameters,
            form_inputs=form_inputs,
            sender_type=(
                model.message.sender.type
                if model.message and model.message.sender
                else None
            ),
            message=(
                MessageRef(name=model.message.name)
                if model.message and model.message.name
                else None
            ),
            source=_action_source(envelope.raw, model, dialog),
            **base,
        )
    if model.type == "WIDGET_UPDATED":
        if not function_name:
            raise InvalidInteractionPayload(
                "WIDGET_UPDATED requires an associated invoked function"
            )
        return WidgetUpdatedEvent(
            function_name=function_name,
            parameters=parameters,
            form_inputs=form_inputs,
            **base,
        )
    if model.type == "APP_COMMAND":
        metadata = model.app_command_metadata
        if (
            metadata is None
            or metadata.app_command_id is None
            or metadata.app_command_type is None
        ):
            raise InvalidInteractionPayload(
                "APP_COMMAND requires appCommandMetadata ID and type"
            )
        kind = _app_command_kind(metadata.app_command_type)
        return CommandEvent(
            command_id=metadata.app_command_id,
            command_type=metadata.app_command_type,
            source_kind=metadata.app_command_type,
            kind=kind,
            message_text=model.message.text if model.message else None,
            target_message=(
                MessageRef(name=model.message.name)
                if kind is CommandKind.MESSAGE_ACTION
                and model.message is not None
                and model.message.name is not None
                else None
            ),
            **base,
        )
    _require_actor_space(model.type, actor, space)
    return FormSubmitEvent(
        function_name=function_name,
        parameters=parameters,
        form_inputs=form_inputs,
        **base,
    )


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        result = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise InvalidInteractionPayload(
            f"Invalid eventTime timestamp: {value!r}"
        ) from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidInteractionPayload("eventTime must include a timezone offset")
    return result


def _user(value: UserModel | None) -> UserRef | None:
    if value is None:
        return None
    return UserRef(name=value.name, display_name=value.display_name, type=value.type)


def _space(value: SpaceModel | None) -> SpaceRef | None:
    if value is None:
        return None
    return SpaceRef(
        name=value.name,
        display_name=value.display_name,
        type=value.type,
        space_type=value.space_type,
        single_user_bot_dm=value.single_user_bot_dm,
    )


def _thread(
    value: ThreadModel | None, *, space: SpaceRef | None = None
) -> ThreadRef | None:
    if value is None:
        return None
    return ThreadRef(name=value.name, thread_key=value.thread_key, space=space)


def _dialog(is_dialog: bool | None, type_: str | None) -> DialogMetadata | None:
    if type_ is None:
        if is_dialog is True:
            raise InvalidInteractionPayload(
                "isDialogEvent=true requires a dialogEventType"
            )
        return None
    if is_dialog is False:
        # contradictory envelope — a dialog type without the dialog
        # event flag is malformed input, not a normal interaction.
        raise InvalidInteractionPayload(
            "dialogEventType present requires isDialogEvent=true"
        )
    try:
        normalized: DialogEventType | str = DialogEventType(type_)
    except ValueError:
        normalized = type_
    return DialogMetadata(type=normalized, is_dialog_event=True)


def _action_source(
    raw: Mapping[str, object],
    model: InteractionModel,
    dialog: DialogMetadata | None,
) -> ActionSource | None:
    """Derive only source facts the official envelope makes unambiguous."""
    if dialog is not None:
        return ActionSource.DIALOG
    if isinstance(raw.get("chat"), Mapping):
        return ActionSource.HOME
    if model.message is not None:
        return ActionSource.MESSAGE
    return None


def _app_command_kind(value: str) -> CommandKind | None:
    # Slash commands have a different documented wire family
    # (MESSAGE + message.slashCommand), so APP_COMMAND/SLASH_COMMAND is
    # retained in raw/source_kind but not promoted into typed routing.
    if value == CommandKind.QUICK_COMMAND:
        return CommandKind.QUICK_COMMAND
    if value == CommandKind.MESSAGE_ACTION:
        return CommandKind.MESSAGE_ACTION
    return None


def _common_action(
    model: InteractionModel,
) -> tuple[dict[str, str], FormInputs, str]:
    common_parameters = dict(model.common.parameters) if model.common else {}
    common_function = model.common.invoked_function if model.common else None
    raw_inputs = model.common.form_inputs if model.common else {}
    form_inputs = parse_form_inputs(raw_inputs)

    legacy_parameters: dict[str, str] = {}
    legacy_function = None
    if model.action:
        legacy_function = model.action.action_method_name
        for item in model.action.parameters:
            if item.key in legacy_parameters:
                raise InvalidInteractionPayload(
                    f"Duplicate legacy action parameter {item.key!r}"
                )
            legacy_parameters[item.key] = item.value
    if (
        common_parameters
        and legacy_parameters
        and common_parameters != legacy_parameters
    ):
        raise ConflictingEnvelopeError(
            "common.parameters conflicts with legacy action.parameters"
        )
    if common_function and legacy_function and common_function != legacy_function:
        raise ConflictingEnvelopeError(
            "common.invokedFunction conflicts with legacy action.actionMethodName"
        )
    return (
        common_parameters or legacy_parameters,
        form_inputs,
        common_function or legacy_function or "",
    )


def _require_actor_space(
    event_type: str, actor: UserRef | None, space: SpaceRef | None
) -> None:
    if actor is None or space is None:
        raise InvalidInteractionPayload(f"{event_type} requires user and space")


def _slash_command_event(model: InteractionModel, base: _EventKwargs) -> CommandEvent:
    """A documented slash command: MESSAGE + message.slashCommand.

    The command id travels as an int64 string; argumentText is the
    mention-stripped body (message.text is the raw body).
    """
    message = model.message
    assert message is not None and message.slash_command is not None
    raw_id = message.slash_command.command_id
    if raw_id is None:
        raise InvalidInteractionPayload("MESSAGE slashCommand requires commandId")
    try:
        command_id = int(raw_id)
    except ValueError as error:
        raise InvalidInteractionPayload(
            f"slashCommand commandId is not an int64 string: {raw_id!r}"
        ) from error
    return CommandEvent(
        command_id=command_id,
        command_type=None,
        source_kind=CommandKind.SLASH_COMMAND,
        kind=CommandKind.SLASH_COMMAND,
        message_text=message.argument_text or message.text,
        **base,
    )


__all__ = ["parse_interaction"]
