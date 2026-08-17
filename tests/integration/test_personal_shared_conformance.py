"""Personal/private and shared interaction conformance gates.

The wire fixtures are minimized from Google's stable Event, command, form,
private-message, and Pub/Sub documentation. Their field-level provenance is
recorded in ``tests/fixtures/google_chat/conformance/README.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI
from google.apps.chat_v1.types.message import CreateMessageRequest
from google.auth.credentials import AnonymousCredentials

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.auth import AuthMode
from chattice.capabilities import (
    ResponseCapabilities,
    ResponseCapability,
)
from chattice.cards import Card, CardHeader, Dialog, Section, TextParagraph
from chattice.client import Bot
from chattice.events import (
    ActionEvent,
    ActionSource,
    AppHomeEvent,
    CommandEvent,
    Event,
    StringInput,
)
from chattice.forms import FormModel
from chattice.fsm import (
    FSMContext,
    FSMStrategy,
    MemoryStorage,
    State,
    StateFilter,
    StatesGroup,
    StorageKey,
)
from chattice.integrations.fastapi import create_chat_router
from chattice.testing import FakeChatTransport, MockBot
from chattice.transports.http import MockVerifier
from chattice.transports.pubsub_runner import (
    DIALOG_UNSUPPORTED_MESSAGE,
    PubSubPullRunner,
)

_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "google_chat" / "conformance"
_INTERACTION_FIXTURE_DIR = _FIXTURE_DIR.parent / "interactions"


def _fixture(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8")),
    )


def _interaction_fixture(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads((_INTERACTION_FIXTURE_DIR / name).read_text(encoding="utf-8")),
    )


def _card(title: str) -> Card:
    return Card(
        header=CardHeader(title=title),
        sections=[Section(widgets=[TextParagraph(title)])],
    )


def _set_message_name(payload: dict[str, object], name: str) -> None:
    message = cast(dict[str, object], payload["message"])
    message["name"] = name


class _Delivery:
    """Minimal google-cloud-pubsub subscriber Message double."""

    def __init__(self, payload: dict[str, object], message_id: str) -> None:
        self.data = json.dumps(payload)
        self.message_id = message_id
        self.delivery_attempt = 0
        self.acked = False
        self.nacked = False

    def ack(self) -> None:
        self.acked = True

    def nack(self) -> None:
        self.nacked = True


async def _deliver(
    runner: PubSubPullRunner,
    payload: dict[str, object],
    message_id: str,
) -> _Delivery:
    delivery = _Delivery(payload, message_id)
    await runner._handle(delivery)
    assert delivery.acked is True
    assert delivery.nacked is False
    return delivery


@dataclass
class PersonalForm(FormModel):
    decision: StringInput


class PersonalFlow(StatesGroup):
    action = State()
    form = State()


async def test_http_native_command_sends_private_card_without_thread() -> None:
    """HTTP command handling uses explicit private outbound Message semantics."""
    credentials = AnonymousCredentials()  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(credentials=credentials)
    bot = Bot(
        credentials=credentials,
        auth_mode=AuthMode.APP,
        transport=transport,
    )
    router = Router()
    seen: list[CommandEvent] = []

    @router.quick_command()
    async def private_command(event: CommandEvent) -> None:
        assert event.space is not None
        assert event.actor is not None
        seen.append(event)
        await event.space.send(card=_card("Private"), private_to=event.actor)

    dispatcher = Dispatcher(bot=bot)
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/", json=_fixture("private_command.json"))

    assert response.status_code == 200
    assert response.content == b""
    assert len(seen) == 1
    request = transport.requests[-1]
    assert request.parent == "spaces/TEAM"
    assert request.message.private_message_viewer.name == "users/123"
    assert request.message.cards_v2[0].card.header.title == "Private"
    assert request.message.thread.name == ""
    assert request.message.thread.thread_key == ""
    reply_option = CreateMessageRequest.MessageReplyOption
    assert request.message_reply_option is reply_option.MESSAGE_REPLY_OPTION_UNSPECIFIED


async def test_private_card_button_decodes_to_typed_action() -> None:
    event = parse_interaction(_fixture("private_card_button.json"))

    assert isinstance(event, ActionEvent)
    assert event.name == "personal.advance"
    assert event.source is ActionSource.MESSAGE
    assert event.actor is not None and event.actor.name == "users/123"
    assert event.message is not None
    assert event.message.name == "spaces/TEAM/messages/PRIVATE"
    assert event.thread is None
    raw = cast(dict[str, object], event.raw)
    message = cast(dict[str, object], raw["message"])
    viewer = cast(dict[str, object], message["privateMessageViewer"])
    assert viewer["name"] == "users/123"


async def test_private_card_form_decodes_to_form_model() -> None:
    router = Router()
    seen: list[PersonalForm] = []

    @router.action("personal.submit", PersonalForm.filter())
    async def submit(event: ActionEvent, form: PersonalForm) -> str:
        seen.append(form)
        return form.decision.values[0]

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(
        parse_interaction(_fixture("private_card_form.json"))
    )

    assert result == "approve"
    assert seen == [PersonalForm(decision=StringInput(values=("approve",)))]


async def test_http_private_card_action_updates_originating_message() -> None:
    router = Router()
    targets: list[str] = []

    @router.action("personal.advance")
    async def advance(event: ActionEvent) -> Card:
        assert event.message is not None and event.message.name is not None
        targets.append(event.message.name)
        return _card("Updated private card")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/", json=_fixture("private_card_button.json"))

    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    assert targets == ["spaces/TEAM/messages/PRIVATE"]
    assert body["actionResponse"] == {"type": "UPDATE_MESSAGE"}
    assert body["cardsV2"][0]["card"]["header"]["title"] == ("Updated private card")


async def test_pubsub_private_command_action_form_and_same_card_update() -> None:
    """Pub/Sub uses private create + whole-Message update, never sync returns."""
    storage = MemoryStorage()
    bot = MockBot()
    router = Router()
    capabilities_seen: list[ResponseCapabilities] = []
    created_names: list[str] = []

    @router.quick_command()
    async def private_command(
        event: CommandEvent,
        state: FSMContext,
        capabilities: ResponseCapabilities,
    ) -> None:
        assert event.space is not None and event.actor is not None
        capabilities_seen.append(capabilities)
        await state.set_state(PersonalFlow.action)
        created = await event.space.send(
            card=_card("Private Pub/Sub"), private_to=event.actor
        )
        created_names.append(created.name)

    @router.action("personal.advance", StateFilter(PersonalFlow.action))
    async def advance(
        event: ActionEvent,
        state: FSMContext,
        capabilities: ResponseCapabilities,
    ) -> Card:
        capabilities_seen.append(capabilities)
        await state.set_state(PersonalFlow.form)
        return _card("Private form")

    @router.action(
        "personal.submit",
        StateFilter(PersonalFlow.form),
        PersonalForm.filter(),
    )
    async def submit(
        event: ActionEvent,
        state: FSMContext,
        form: PersonalForm,
        capabilities: ResponseCapabilities,
    ) -> Card:
        capabilities_seen.append(capabilities)
        assert form.decision.values == ("approve",)
        await state.finish()
        return _card("Private complete")

    dispatcher = Dispatcher(fsm_storage=storage)
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/private",
        bot=cast(Bot, bot),
    )

    await _deliver(runner, _fixture("private_command.json"), "private-command")
    assert len(created_names) == 1
    button_payload = _fixture("private_card_button.json")
    form_payload = _fixture("private_card_form.json")
    _set_message_name(button_payload, created_names[0])
    _set_message_name(form_payload, created_names[0])
    await _deliver(runner, button_payload, "private-button")
    await _deliver(runner, form_payload, "private-form")

    assert len(capabilities_seen) == 3
    assert all(
        ResponseCapability.SYNC_RESPONSE not in capabilities
        for capabilities in capabilities_seen
    )
    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert len(sent) == 1
    assert sent[0]["space"] == "spaces/TEAM"
    assert sent[0]["private_to"] == "users/123"
    assert sent[0]["card"]["header"]["title"] == "Private Pub/Sub"
    updates = [args for kind, args in bot.calls if kind == "update_message"]
    assert [update["name"] for update in updates] == created_names * 2
    assert [update["card"]["header"]["title"] for update in updates] == [
        "Private form",
        "Private complete",
    ]
    completed_event = parse_interaction(form_payload)
    key = StorageKey.build(completed_event, FSMStrategy.USER_IN_SPACE)
    assert key is not None
    assert await storage.get_state(key) is None


async def test_shared_thread_card_and_state_are_shared_across_two_users() -> None:
    storage = MemoryStorage()
    bot = MockBot()
    router = Router()
    parsed_events: list[ActionEvent] = []

    @router.action("shared.vote")
    async def vote(event: ActionEvent, state: FSMContext) -> Card:
        assert event.space is not None and event.space.name is not None
        assert event.thread is not None and event.thread.name is not None
        assert event.message is not None and event.message.name is not None
        parsed_events.append(event)

        personal = await state.get_data()
        personal_clicks = personal.get("clicks", 0)
        assert isinstance(personal_clicks, int)
        await state.set_data({"clicks": personal_clicks + 1})

        shared_key = StorageKey(
            user=None,
            space=event.space.name,
            thread=event.thread.name,
        )
        shared = await storage.get_data(shared_key)
        total = shared.get("total", 0)
        assert isinstance(total, int)
        total += 1
        await storage.set_data(shared_key, {"total": total})
        return _card(f"Shared total: {total}")

    dispatcher = Dispatcher(fsm_storage=storage)
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/shared",
        bot=cast(Bot, bot),
    )

    await _deliver(
        runner,
        _fixture("shared_thread_card_click_alice.json"),
        "shared-alice",
    )
    await _deliver(
        runner,
        _fixture("shared_thread_card_click_bob.json"),
        "shared-bob",
    )

    updates = [args for kind, args in bot.calls if kind == "update_message"]
    assert [update["name"] for update in updates] == [
        "spaces/TEAM/messages/SHARED",
        "spaces/TEAM/messages/SHARED",
    ]
    assert [update["card"]["header"]["title"] for update in updates] == [
        "Shared total: 1",
        "Shared total: 2",
    ]

    personal_keys = [
        StorageKey.build(event, FSMStrategy.USER_IN_SPACE) for event in parsed_events
    ]
    assert None not in personal_keys
    alice_key = cast(StorageKey, personal_keys[0])
    bob_key = cast(StorageKey, personal_keys[1])
    assert alice_key != bob_key
    assert await storage.get_data(alice_key) == {"clicks": 1}
    assert await storage.get_data(bob_key) == {"clicks": 1}
    shared_key = StorageKey(
        user=None,
        space="spaces/TEAM",
        thread="spaces/TEAM/threads/WORKFLOW",
    )
    assert await storage.get_data(shared_key) == {"total": 2}


def test_storage_key_expresses_all_required_scope_combinations() -> None:
    """No THREAD_USER enum is needed: StorageKey already carries all axes."""
    user = "users/alice"
    space = "spaces/TEAM"
    thread = "spaces/TEAM/threads/WORKFLOW"

    assert StorageKey(user=user, space=None, thread=None)  # USER
    assert StorageKey(user=user, space=space, thread=None)  # SPACE_USER
    assert StorageKey(user=None, space=space, thread=thread)  # THREAD
    assert StorageKey(user=None, space=space, thread=None)  # SPACE
    assert StorageKey(user=user, space=space, thread=thread)  # THREAD_USER


async def test_dm_interactive_card_updates_same_message_through_pubsub() -> None:
    bot = MockBot()
    router = Router()
    seen: list[ActionEvent] = []

    @router.action("dm.advance")
    async def advance(event: ActionEvent) -> Card:
        seen.append(event)
        return _card("DM updated")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/dm",
        bot=cast(Bot, bot),
    )
    await _deliver(runner, _fixture("dm_card_click.json"), "dm-action")

    assert len(seen) == 1
    assert seen[0].space is not None
    assert seen[0].space.space_type == "DIRECT_MESSAGE"
    assert seen[0].space.single_user_bot_dm is True
    assert seen[0].thread is None
    updates = [args for kind, args in bot.calls if kind == "update_message"]
    assert len(updates) == 1
    assert updates[0]["name"] == "spaces/DM/messages/CARD"
    assert updates[0]["card"]["header"]["title"] == "DM updated"
    assert not [args for kind, args in bot.calls if kind == "send_message"]


async def test_dialog_over_pubsub_fails_closed_with_capability_message() -> None:
    bot = MockBot()
    router = Router()

    @router.action("personal.advance")
    async def dialog(event: ActionEvent) -> Dialog:
        return Dialog(body=_card("Unsupported"))

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    runner = PubSubPullRunner(
        dispatcher,
        "projects/P/subscriptions/dialog",
        bot=cast(Bot, bot),
    )
    await _deliver(runner, _fixture("private_card_button.json"), "dialog")

    sent = [args for kind, args in bot.calls if kind == "send_message"]
    assert len(sent) == 1
    assert sent[0]["text"] == DIALOG_UNSUPPORTED_MESSAGE
    assert sent[0]["card"] is None


def test_app_home_is_http_only_in_transport_matrix() -> None:
    event: Event = parse_interaction(_interaction_fixture("app_home.json"))
    assert isinstance(event, AppHomeEvent)

    http = ResponseCapabilities.resolve(transport="http", event=event)
    pubsub = ResponseCapabilities.resolve(transport="pubsub", event=event)
    assert ResponseCapability.APP_HOME in http
    assert ResponseCapability.APP_HOME not in pubsub
    assert ResponseCapability.SYNC_RESPONSE not in pubsub
