"""Additive public-beta DX enrichment contracts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import pytest
from google.apps.chat_v1.types.message import Message

from chattice import Dispatcher, Router
from chattice.actions import ActionData
from chattice.adapters.google_chat import parse_interaction
from chattice.cards import Button
from chattice.client import MessageReplyOption
from chattice.events import MessageEvent, SpaceRef, ThreadRef


class _RecordingBot:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str | None, dict[str, object]]] = []

    async def send_message(
        self,
        space: object,
        text: str | None = None,
        **kwargs: object,
    ) -> Message:
        self.calls.append((space, text, kwargs))
        return Message(name="spaces/A/messages/out", text=text or "")


def _message_event(**message_fields: object) -> MessageEvent:
    payload: dict[str, object] = {
        "type": "MESSAGE",
        "space": {"name": "spaces/A"},
        "message": {
            "name": "spaces/A/messages/M",
            "text": "hello",
            "sender": {"type": "HUMAN"},
            "thread": {"name": "spaces/A/threads/T"},
            **message_fields,
        },
    }
    return cast(MessageEvent, parse_interaction(payload))


async def test_contextual_sends_delegate_to_one_bot_without_fetches() -> None:
    bot = _RecordingBot()
    router = Router()

    @router.message()
    async def handle(message: MessageEvent) -> None:
        assert message.space is not None
        assert message.thread is not None
        await message.reply("reply")
        await message.thread.send("thread")
        await message.space.send("space")

    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)
    original = _message_event()
    await dispatcher.feed_update(original)

    assert [text for _space, text, _kwargs in bot.calls] == [
        "reply",
        "thread",
        "space",
    ]
    reply_thread = cast(ThreadRef, bot.calls[0][2]["thread"])
    assert reply_thread.name == "spaces/A/threads/T"
    assert bot.calls[0][2]["reply_option"] is MessageReplyOption.REPLY_OR_FAIL
    assert bot.calls[1][2]["reply_option"] is (
        MessageReplyOption.REPLY_FALLBACK_TO_NEW_THREAD
    )
    assert bot.calls[2][2]["thread"] is None
    # Binding is request-local; the immutable source event remains unbound.
    with pytest.raises(RuntimeError, match="requires a Bot"):
        await original.reply("outside")


async def test_contextual_bot_binding_is_task_local() -> None:
    first = _RecordingBot()
    second = _RecordingBot()
    router = Router()

    @router.message()
    async def handle(message: MessageEvent) -> None:
        await asyncio.sleep(0)
        await message.reply(message.text)

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await asyncio.gather(
        dispatcher.feed_update(_message_event(text="first"), bot=first),
        dispatcher.feed_update(_message_event(text="second"), bot=second),
    )

    assert [call[1] for call in first.calls] == ["first"]
    assert [call[1] for call in second.calls] == ["second"]


async def test_refs_support_explicit_bot_and_never_resolve_resources() -> None:
    bot = _RecordingBot()

    await SpaceRef(name="spaces/A").send("space", bot=bot)
    await ThreadRef(name="spaces/A/threads/T").send("thread", bot=bot)
    await ThreadRef(thread_key="customer-42", space=SpaceRef(name="spaces/A")).send(
        "key", bot=bot
    )

    assert [text for _space, text, _kwargs in bot.calls] == [
        "space",
        "thread",
        "key",
    ]
    assert bot.calls[1][0] == "spaces/A"
    assert cast(ThreadRef, bot.calls[2][2]["thread"]).thread_key == "customer-42"


def test_thread_parent_enrichment_preserves_legacy_value_semantics() -> None:
    legacy = ThreadRef(name="spaces/A/threads/T")
    enriched = ThreadRef(name="spaces/A/threads/T", space=SpaceRef(name="spaces/A"))

    assert enriched == legacy
    assert hash(enriched) == hash(legacy)
    assert repr(enriched) == repr(legacy)


async def test_thread_send_rejects_unknown_parent_without_network() -> None:
    bot = _RecordingBot()

    with pytest.raises(RuntimeError, match="requires its parent space"):
        await ThreadRef(thread_key="key").send("x", bot=bot)

    assert bot.calls == []


def test_message_read_accessors_are_lossless_immutable_snapshots() -> None:
    event = _message_event(
        attachment=[{"name": "attachments/1", "contentName": "report.pdf"}],
        annotations=[
            {
                "type": "USER_MENTION",
                "startIndex": 0,
                "length": 4,
                "userMention": {
                    "user": {"name": "users/1", "displayName": "Ada"},
                    "type": "MENTION",
                },
            },
            {"type": "RICH_LINK", "richLinkMetadata": {"uri": "https://x"}},
        ],
        quotedMessageMetadata={
            "name": "spaces/A/messages/Q",
            "quoteType": "REPLY",
        },
        emojiReactionSummaries=[{"emoji": {"unicode": "👍"}, "reactionCount": 2}],
        privateMessageViewer={"name": "users/1"},
        silent=True,
    )

    assert event.attachments[0]["contentName"] == "report.pdf"
    assert len(event.annotations) == 2
    assert event.mentions == (event.annotations[0],)
    assert event.mentions[0]["startIndex"] == 0
    assert event.quote == {
        "name": "spaces/A/messages/Q",
        "quoteType": "REPLY",
    }
    assert event.reaction_summaries[0]["reactionCount"] == 2
    assert event.is_private is True
    assert event.is_silent is True

    with pytest.raises(TypeError):
        cast(Any, event.attachments[0])["name"] = "changed"
    user_mention = cast(dict[str, object], event.mentions[0]["userMention"])
    with pytest.raises(TypeError):
        cast(Any, user_mention)["type"] = "ADD"


def test_message_read_accessors_handle_absent_and_wrapped_fields() -> None:
    plain = _message_event()
    assert plain.attachments == ()
    assert plain.annotations == ()
    assert plain.mentions == ()
    assert plain.quote is None
    assert plain.reaction_summaries == ()
    assert plain.is_private is False
    assert plain.is_silent is False

    wrapped = cast(
        MessageEvent,
        parse_interaction(
            {
                "chat": {
                    "type": "MESSAGE",
                    "space": {"name": "spaces/A"},
                    "message": {
                        "text": "quiet",
                        "thread": {"name": "spaces/A/threads/T"},
                        "silent": True,
                    },
                }
            }
        ),
    )
    assert wrapped.is_silent is True


@dataclass
class Deploy(ActionData, function="deploy.confirm"):
    environment: str
    replicas: int = 1


def test_button_binds_action_data_without_packed_callback_string() -> None:
    button = Button("Deploy", action=Deploy(environment="prod", replicas=3)).to_proto()

    assert button.on_click.action.function == "deploy.confirm"
    assert [(item.key, item.value) for item in button.on_click.action.parameters] == [
        ("environment", "prod"),
        ("replicas", "3"),
    ]


def test_button_keeps_low_level_action_form_and_rejects_ambiguous_binding() -> None:
    low_level = Button(
        "Deploy", action="deploy.confirm", parameters={"environment": "prod"}
    ).to_proto()
    assert low_level.on_click.action.function == "deploy.confirm"

    @dataclass
    class Unbound(ActionData):
        value: str

    with pytest.raises(ValueError, match="requires a Google action function"):
        Button("X", action=Unbound("x"))
    with pytest.raises(ValueError, match="parameters must be omitted"):
        Button("X", action=Deploy("prod"), parameters={"extra": "x"})


def test_action_data_rejects_empty_function_discriminator() -> None:
    with pytest.raises(ValueError, match="non-empty"):

        @dataclass
        class Invalid(ActionData, function=" "):
            value: str
