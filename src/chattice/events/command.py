"""Chat app command interaction event."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .base import Event
from .references import MessageRef


class CommandKind(StrEnum):
    """Google-native command families, independent of their wire envelope."""

    SLASH_COMMAND = "SLASH_COMMAND"
    QUICK_COMMAND = "QUICK_COMMAND"
    MESSAGE_ACTION = "MESSAGE_ACTION"


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandEvent(Event):
    """A command identified by configured numeric ID and documented type.

    Produced from BOTH wire families:
    - slash commands arrive as ``MESSAGE`` events with
      ``message.slashCommand`` + ``argumentText`` (source kind
      ``SLASH_COMMAND``);
    - quick commands / message actions arrive as ``APP_COMMAND`` events
      with ``appCommandMetadata`` (source kind ``QUICK_COMMAND``;
      ``MESSAGE_ACTION`` is a Developer Preview type, accepted
      forward-compatibly).
    """

    event_type: str = field(default="command", init=False)
    command_id: int
    command_type: str | None = None
    kind: CommandKind | None = None
    # Compatibility field retained for pre-beta callers. New code should
    # compare the typed ``kind`` value.
    source_kind: str | None = None
    message_text: str | None = None
    target_message: MessageRef | None = None

    def __post_init__(self) -> None:
        kind = self.kind
        source_kind = self.source_kind
        source_kind_value: CommandKind | None = None
        if source_kind is not None:
            try:
                source_kind_value = CommandKind(source_kind)
            except ValueError:
                source_kind_value = None
        if (
            kind is not None
            and source_kind_value is not None
            and kind != source_kind_value
        ):
            raise ValueError("kind and source_kind describe different command families")
        if source_kind is None and kind is not None:
            source_kind = kind.value
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "source_kind", source_kind)


__all__ = ["CommandEvent", "CommandKind"]
