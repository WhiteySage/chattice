# ruff: noqa: ASYNC109 — timeout mirrors Bot.send_message
"""Small immutable references extracted from interaction payloads."""

from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from google.apps.chat_v1.types.message import Message

    from chattice.cards import AccessoryWidget, Card
    from chattice.client import MessageReplyOption


_current_bot: ContextVar[object | None] = ContextVar(
    "chattice_current_bot", default=None
)


def _set_current_bot(bot: object | None) -> Token[object | None]:
    return _current_bot.set(bot)


def _reset_current_bot(token: Token[object | None]) -> None:
    _current_bot.reset(token)


def _message_sender(explicit: object | None) -> Any:
    sender = explicit if explicit is not None else _current_bot.get()
    if sender is None or not callable(getattr(sender, "send_message", None)):
        raise RuntimeError(
            "Contextual send requires a Bot. Configure Dispatcher(bot=...), "
            "pass bot=... to Dispatcher.feed_update(), or pass bot=... to "
            "this method."
        )
    return sender


async def _send_message(
    explicit: object | None,
    space: SpaceRef | str,
    text: str | None,
    *,
    thread: ThreadRef | None,
    reply_option: MessageReplyOption | None,
    request_id: str | None,
    message_id: str | None,
    timeout: float | None,
    accessory_widgets: Sequence[AccessoryWidget] | None,
    card: Card | None,
    notify: str | None,
    private_to: UserRef | str | None,
) -> Message:
    # Local import avoids the client -> event-reference import cycle.
    from chattice.client import MessageReplyOption

    option = reply_option or MessageReplyOption.REPLY_FALLBACK_TO_NEW_THREAD
    sender = _message_sender(explicit)
    result = await sender.send_message(
        space,
        text,
        thread=thread,
        reply_option=option,
        request_id=request_id,
        message_id=message_id,
        timeout=timeout,
        accessory_widgets=accessory_widgets,
        card=card,
        notify=notify,
        private_to=private_to,
    )
    return cast("Message", result)


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRef:
    """Stable user identity and optional presentation metadata."""

    name: str | None = None
    display_name: str | None = None
    type: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SpaceRef:
    """Minimal Chat space reference.

    ``space_type`` (DIRECT_MESSAGE / GROUP_CHAT / SPACE) and
    ``single_user_bot_dm`` distinguish the personal bot DM (the Home tab
    host space) from collaborative spaces — the Home DM
    space must never be treated as a publish destination.
    """

    name: str | None = None
    display_name: str | None = None
    type: str | None = None
    space_type: str | None = None
    single_user_bot_dm: bool | None = None

    async def send(
        self,
        text: str | None = None,
        *,
        thread: ThreadRef | None = None,
        reply_option: MessageReplyOption | None = None,
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Sequence[AccessoryWidget] | None = None,
        card: Card | None = None,
        notify: str | None = None,
        private_to: UserRef | str | None = None,
        bot: object | None = None,
    ) -> Message:
        """Send through the bound Bot without fetching this space."""
        return await _send_message(
            bot,
            self,
            text,
            thread=thread,
            reply_option=reply_option,
            request_id=request_id,
            message_id=message_id,
            timeout=timeout,
            accessory_widgets=accessory_widgets,
            card=card,
            notify=notify,
            private_to=private_to,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ThreadRef:
    """Minimal Chat thread reference with an optional known parent space."""

    name: str | None = None
    thread_key: str | None = None
    # Context enrichment must not change legacy ref equality/hash/repr.
    space: SpaceRef | None = field(default=None, repr=False, compare=False)

    def _parent_space(self, explicit: SpaceRef | str | None) -> SpaceRef | str:
        if explicit is not None:
            return explicit
        if self.space is not None:
            return self.space
        if self.name is not None and "/threads/" in self.name:
            parent, _separator, _thread_id = self.name.partition("/threads/")
            if parent.startswith("spaces/"):
                return parent
        raise RuntimeError(
            "ThreadRef.send() requires its parent space. Use a parsed event "
            "thread, construct ThreadRef(..., space=...), or pass space=...."
        )

    async def send(
        self,
        text: str | None = None,
        *,
        space: SpaceRef | str | None = None,
        reply_option: MessageReplyOption | None = None,
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Sequence[AccessoryWidget] | None = None,
        card: Card | None = None,
        notify: str | None = None,
        private_to: UserRef | str | None = None,
        bot: object | None = None,
    ) -> Message:
        """Send in this thread through the bound Bot with zero fetches."""
        return await _send_message(
            bot,
            self._parent_space(space),
            text,
            thread=self,
            reply_option=reply_option,
            request_id=request_id,
            message_id=message_id,
            timeout=timeout,
            accessory_widgets=accessory_widgets,
            card=card,
            notify=notify,
            private_to=private_to,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class MessageRef:
    """Minimal message identity exposed to ordinary handlers."""

    name: str | None = None


__all__ = ["MessageRef", "SpaceRef", "ThreadRef", "UserRef"]
