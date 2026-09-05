"""Example startup and routing use test substitutes for external services.

The executable applications use the normal authenticated APIs. Tests import
them without credentials and replace the subscriber to exercise main() and
handler behavior. The webhook test provides a synthetic audience.
"""

from __future__ import annotations

import importlib

import pytest


def test_echo_bot_imports() -> None:
    module = importlib.import_module("examples.echo_bot")
    assert callable(module.main)


def test_echo_bot_webhook_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATTICE_AUDIENCE", "https://example.test")
    module = importlib.import_module("examples.echo_bot_webhook")
    assert callable(module.main)


def test_error_handling_imports() -> None:
    module = importlib.import_module("examples.error_handling")
    assert callable(module.main)


def test_finite_state_machine_imports() -> None:
    module = importlib.import_module("examples.finite_state_machine")
    assert callable(module.main)


def test_own_filter_imports() -> None:
    module = importlib.import_module("examples.own_filter")
    assert callable(module.main)


def test_specify_updates_imports() -> None:
    module = importlib.import_module("examples.specify_updates")
    assert callable(module.main)


def test_context_addition_from_filter_imports() -> None:
    module = importlib.import_module("examples.context_addition_from_filter")
    assert callable(module.main)


def test_without_dispatcher_imports() -> None:
    module = importlib.import_module("examples.without_dispatcher")
    assert callable(module.main)


@pytest.mark.parametrize(
    ("module_name", "messages", "expected"),
    [
        ("echo_bot", ["hello"], ["You said: hello"]),
        (
            "specify_updates",
            ["ping", "hello"],
            ["pong", "echo: hello"],
        ),
        (
            "own_filter",
            ["Ready?", "hello"],
            ["Thinking... ask me later, I am just an example.", "Echo: hello"],
        ),
        (
            "context_addition_from_filter",
            ["topic: support", "hello"],
            ["Queued: support", "Send 'topic: <something>' to see context injection."],
        ),
        (
            "error_handling",
            ["boom", "hello"],
            [
                "Something went wrong (RuntimeError). Try again later.",
                "You said: hello",
            ],
        ),
        (
            "finite_state_machine",
            ["incident", "Network", "urgent", "high", "later", "confirm", "hello"],
            [
                "Incident report started. Send the incident TITLE.",
                "Got the title. Now the SEVERITY (low / medium / high).",
                "Choose low, medium, or high.",
                "Got the severity. Send 'confirm' to finish.",
                "Send 'confirm' to finish.",
                "Done: Network (high) — confirm",
                None,
            ],
        ),
    ],
)
async def test_pull_examples_configure_credentials_and_handle_messages(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    messages: list[str],
    expected: list[str | None],
) -> None:
    from chattice import Dispatcher
    from chattice.auth import CredentialsProvider, ServiceAccountCredentialsProvider
    from chattice.client import Bot
    from chattice.events import MessageEvent, SpaceRef, UserRef

    monkeypatch.setenv("CHATTICE_SERVICE_ACCOUNT_FILE", "service-account.json")
    monkeypatch.setenv("CHATTICE_SUBSCRIPTION", "projects/P/subscriptions/S")
    closed: list[Bot] = []
    outputs: list[object] = []
    original_close = Bot.close

    async def close(bot: Bot) -> None:
        closed.append(bot)
        await original_close(bot)

    async def run(
        dispatcher: Dispatcher,
        subscription: str,
        *,
        bot: Bot,
        credentials_provider: CredentialsProvider,
    ) -> None:
        assert subscription == "projects/P/subscriptions/S"
        assert isinstance(credentials_provider, ServiceAccountCredentialsProvider)
        assert credentials_provider.file_path == "service-account.json"
        assert credentials_provider.scopes == (
            "https://www.googleapis.com/auth/pubsub",
        )
        for text in messages:
            outputs.append(
                await dispatcher.feed_update(
                    MessageEvent(
                        text=f"@App {text}"
                        if text in {"ping", "boom", "incident", "topic: support"}
                        else text,
                        argument_text=text,
                        space=SpaceRef(name="spaces/A"),
                        actor=UserRef(name="users/1"),
                    ),
                    bot=bot,
                )
            )

    monkeypatch.setattr(Bot, "close", close)
    monkeypatch.setattr(Dispatcher, "run_pubsub", run)
    await importlib.import_module(f"examples.{module_name}").main()

    assert outputs == expected
    assert len(closed) == 1


async def test_pull_example_closes_bot_when_subscriber_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from chattice import Dispatcher
    from chattice.client import Bot

    monkeypatch.setenv("CHATTICE_SERVICE_ACCOUNT_FILE", "service-account.json")
    monkeypatch.setenv("CHATTICE_SUBSCRIPTION", "projects/P/subscriptions/S")
    closed: list[Bot] = []

    async def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("subscriber unavailable")

    async def close(bot: Bot) -> None:
        closed.append(bot)

    monkeypatch.setattr(Dispatcher, "run_pubsub", fail)
    monkeypatch.setattr(Bot, "close", close)
    with pytest.raises(RuntimeError, match="subscriber unavailable"):
        await importlib.import_module("examples.echo_bot").main()
    assert len(closed) == 1


async def test_without_dispatcher_runs_message_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    from chattice.auth import ServiceAccountCredentialsProvider
    from chattice.testing import MockBot

    class ExampleBot(MockBot):
        closed = False

        async def close(self) -> None:
            self.closed = True

    bot = ExampleBot()

    def make_bot(
        *, app_credentials_provider: ServiceAccountCredentialsProvider
    ) -> ExampleBot:
        assert app_credentials_provider.file_path == "service-account.json"
        return bot

    module = importlib.import_module("examples.without_dispatcher")
    monkeypatch.setenv("CHATTICE_SERVICE_ACCOUNT_FILE", "service-account.json")
    monkeypatch.setattr(sys, "argv", ["without_dispatcher.py", "spaces/A"])
    monkeypatch.setattr(module, "Bot", make_bot)
    await module.main()

    assert bot.closed
    assert [name for name, _args in bot.calls] == [
        "send_message",
        "update_message",
        "get_message",
        "delete_message",
    ]
