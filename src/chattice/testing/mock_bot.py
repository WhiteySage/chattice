# ruff: noqa: ASYNC109 — timeout kwarg mirrors the real Bot (gapic call convention)
"""MockBot: a call-recording stand-in for the outgoing API."""

from __future__ import annotations

from typing import Any

from google.apps.chat_v1.types.message import Message
from google.apps.chat_v1.types.space import Space

from chattice.auth import AuthMode
from chattice.capabilities import OutboundCapabilities

__all__ = ["MockBot"]


class MockBot:
    """Records outgoing calls and fabricates SDK proto responses.

    No transport, no network. DI-compatible with the real Bot: handlers
    receive it by name (``feed_update(event, bot=mock_bot)``).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def capabilities(self) -> OutboundCapabilities:
        """Mirror a real app-authenticated Bot."""
        return OutboundCapabilities.resolve(AuthMode.APP)

    async def send_message(
        self,
        space: Any,
        text: str | None = None,
        *,
        thread: Any = None,
        reply_option: Any = None,
        request_id: str | None = None,
        message_id: str | None = None,
        timeout: float | None = None,
        accessory_widgets: Any = None,
        card: Any = None,
        notify: Any = None,
        private_to: Any = None,
    ) -> Message:
        parent = space if isinstance(space, str) else space.name
        self.calls.append(
            (
                "send_message",
                {
                    "space": parent,
                    "text": text,
                    "card": card.to_dict() if card is not None else None,
                    "notify": notify,
                    "private_to": (
                        private_to.name if hasattr(private_to, "name") else private_to
                    ),
                },
            )
        )
        name = f"{parent}/messages/{len(self.calls)}"
        return Message(name=name, text=text or "")

    async def get_message(self, name: str, *, timeout: float | None = None) -> Message:
        self.calls.append(("get_message", {"name": name}))
        return Message(name=name, text="")

    async def update_message(
        self,
        name: str,
        text: str | None = None,
        *,
        card: Any = None,
        timeout: float | None = None,
    ) -> Message:
        # Mirrors the real Bot.update_message(name, text=None, *, card=...):
        # the card path records the card payload (live dogfooding gap —
        # the mirror lagged behind the real client and dropped card=).
        self.calls.append(
            (
                "update_message",
                {
                    "name": name,
                    "text": text,
                    "card": card.to_dict() if card is not None else None,
                },
            )
        )
        return Message(name=name, text=text or "")

    async def delete_message(self, name: str, *, timeout: float | None = None) -> None:
        self.calls.append(("delete_message", {"name": name}))

    async def get_space(self, name: str, *, timeout: float | None = None) -> Space:
        self.calls.append(("get_space", {"name": name}))
        return Space(name=name)

    def _sent_texts(self) -> list[str]:
        return [
            args["text"] or "" for kind, args in self.calls if kind == "send_message"
        ]

    def assert_message_sent(self, text: str | None = None, *, count: int = 1) -> None:
        """Assert send_message was called `count` times (optionally with text)."""
        sent = self._sent_texts()
        if len(sent) != count:
            raise AssertionError(
                f"expected {count} sent message(s), got {len(sent)}: {sent!r}"
            )
        if text is not None and sent != [text] * count:
            raise AssertionError(f"expected sent text {text!r} x{count}, got {sent!r}")

    def assert_updated(self, name: str, text: str) -> None:
        """Assert update_message was called with the given name/text."""
        for kind, args in self.calls:
            if (
                kind == "update_message"
                and args.get("name") == name
                and args.get("text") == text
            ):
                return
        raise AssertionError(
            f"expected update_message({name!r}, {text!r}), "
            f"calls: {[(k, a) for k, a in self.calls if k == 'update_message']!r}"
        )

    def assert_no_messages(self) -> None:
        """Assert nothing was sent."""
        sent = self._sent_texts()
        if sent:
            raise AssertionError(f"expected no sent messages, got {sent!r}")
