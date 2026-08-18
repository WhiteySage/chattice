# ruff: noqa: ASYNC109 — timeout mirrors Bot.send_message
"""Message domain event."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from google.apps.chat_v1.types.message import Message

    from chattice.cards import AccessoryWidget, Card
    from chattice.client import MessageReplyOption
    from chattice.media import InputFile, UploadedAttachment

from chattice.media import AttachmentRef

from .base import Event
from .references import MessageRef, UserRef, _send_message


def _raw_message(raw: object) -> Mapping[str, object]:
    if not isinstance(raw, Mapping):
        return {}
    event: Mapping[object, object] = raw
    wrapped = raw.get("chat")
    if isinstance(wrapped, Mapping):
        event = wrapped
    message = event.get("message")
    if not isinstance(message, Mapping):
        return {}
    return cast(Mapping[str, object], message)


def _immutable_snapshot(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _immutable_snapshot(item) for key, item in value.items()}
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_immutable_snapshot(item) for item in value)
    return deepcopy(value)


def _mapping_snapshot(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], _immutable_snapshot(value))


def _mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    snapshots: list[Mapping[str, object]] = []
    for item in value:
        snapshot = _mapping_snapshot(item)
        if snapshot is not None:
            snapshots.append(snapshot)
    return tuple(snapshots)


@dataclass(frozen=True, slots=True, kw_only=True)
class MessageEvent(Event):
    """A normalized Chat message interaction.

    ``text`` is Google's raw text; ``argument_text`` (when present) is the
    documented mention-stripped body — route on it to handle
    ``@MyApp ping`` as ``ping`` without a custom mention parser.
    """

    event_type: str = field(default="message", init=False)
    text: str = ""
    message: MessageRef | None = None
    matched_url: str | None = None
    sender_type: str | None = None
    argument_text: str | None = None

    @property
    def attachments(self) -> tuple[Mapping[str, object], ...]:
        """Lossless snapshots of Google's ``message.attachment`` entries."""
        return _mapping_sequence(_raw_message(self.raw).get("attachment"))

    @property
    def attachment_refs(self) -> tuple[AttachmentRef, ...]:
        """Typed inbound attachment metadata (additive over ``attachments``).

        Distinguishes UPLOADED_CONTENT from DRIVE_FILE and exposes the
        human-facing thumbnail/download links next to the programmatic
        ``attachmentDataRef.resourceName`` download handle.
        """
        return tuple(AttachmentRef.from_mapping(m) for m in self.attachments)

    @property
    def annotations(self) -> tuple[Mapping[str, object], ...]:
        """Lossless snapshots of Google's output-only annotations."""
        return _mapping_sequence(_raw_message(self.raw).get("annotations"))

    @property
    def mentions(self) -> tuple[Mapping[str, object], ...]:
        """User-mention annotations, preserving ranges and mention metadata."""
        return tuple(
            annotation
            for annotation in self.annotations
            if annotation.get("type") == "USER_MENTION"
        )

    @property
    def quote(self) -> Mapping[str, object] | None:
        """Lossless ``quotedMessageMetadata`` snapshot, when present."""
        return _mapping_snapshot(_raw_message(self.raw).get("quotedMessageMetadata"))

    @property
    def reaction_summaries(self) -> tuple[Mapping[str, object], ...]:
        """Lossless snapshots of Google's emoji reaction summaries."""
        return _mapping_sequence(_raw_message(self.raw).get("emojiReactionSummaries"))

    @property
    def is_private(self) -> bool:
        """Whether Google marks the message for a private message viewer."""
        return _raw_message(self.raw).get("privateMessageViewer") is not None

    @property
    def is_silent(self) -> bool:
        """Whether Google suppressed push notifications for the message."""
        return _raw_message(self.raw).get("silent") is True

    async def reply(
        self,
        text: str | None = None,
        *,
        reply_option: MessageReplyOption | None = None,
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Sequence[AccessoryWidget] | None = None,
        card: Card | None = None,
        notify: str | None = None,
        private_to: UserRef | str | None = None,
        attachments: Sequence[InputFile | UploadedAttachment] | None = None,
        bot: object | None = None,
    ) -> Message:
        """Reply in this message's known thread through the bound Bot."""
        if self.space is None:
            raise RuntimeError("MessageEvent.reply() requires a known space")
        if self.thread is None:
            raise RuntimeError("MessageEvent.reply() requires a known thread")
        if reply_option is None:
            # A reply to a concrete incoming message must never silently
            # fall back to a new thread.
            from chattice.client import MessageReplyOption

            reply_option = MessageReplyOption.REPLY_OR_FAIL
        return await _send_message(
            bot,
            self.space,
            text,
            thread=self.thread,
            reply_option=reply_option,
            request_id=request_id,
            message_id=message_id,
            timeout=timeout,
            accessory_widgets=accessory_widgets,
            card=card,
            notify=notify,
            private_to=private_to,
            attachments=attachments,
        )
