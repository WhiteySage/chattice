"""Experimental AI bridging contracts (Phase 20)."""

from __future__ import annotations

from typing import Any, cast

from chattice.events import MessageEvent, SpaceRef, UserRef
from chattice.experimental.ai import (
    AgentRequest,
    AgentResponse,
    AgentSession,
    FakeAgent,
    MemoryAgentSessionStorage,
    ToolPolicy,
)


def test_agent_request_from_event() -> None:
    from typing import cast

    from chattice.adapters.google_chat import parse_interaction
    from chattice.events import MessageEvent

    event = cast(
        MessageEvent,
        parse_interaction(
            {
                "type": "MESSAGE",
                "message": {"text": "привет"},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        ),
    )
    request = AgentRequest.from_event(event)
    assert request.text == "привет"
    assert request.context.user == UserRef(name="users/1")
    assert request.context.space == SpaceRef(name="spaces/A")


async def test_fake_agent_echo_and_recording() -> None:
    agent = FakeAgent()
    response = await agent.run(AgentRequest(text="ping"))
    assert isinstance(response, AgentResponse)
    assert response.text == "echo: ping"
    assert len(agent.requests) == 1


async def test_fake_agent_canned_replies() -> None:
    agent = FakeAgent(replies=["первый", "второй"])
    first = await agent.run(AgentRequest(text="a"))
    second = await agent.run(AgentRequest(text="b"))
    assert first.text == "первый"
    assert second.text == "второй"


async def test_session_storage_roundtrip() -> None:
    storage = MemoryAgentSessionStorage()
    assert await storage.get_session("users/1:spaces/A") is None
    session = AgentSession(session_id="s-1", data={"lang": "ru"})
    await storage.save_session("users/1:spaces/A", session)
    loaded = await storage.get_session("users/1:spaces/A")
    assert loaded is not None and loaded.session_id == "s-1"
    assert dict(loaded.data) == {"lang": "ru"}


def test_tool_policy_defaults_read_only_empty() -> None:
    policy = ToolPolicy()
    assert policy.allowed_tools == frozenset()
    assert policy.allow_writes is False
    explicit = ToolPolicy(allowed_tools=frozenset({"search"}), allow_writes=True)
    assert "search" in explicit.allowed_tools


async def test_agent_inside_handler() -> None:
    from chattice import Dispatcher, Router

    agent = FakeAgent()
    router = Router()

    @router.message()
    async def assistant(message: MessageEvent, backend: FakeAgent) -> str:
        result = await backend.run(
            AgentRequest.from_event(message), tool_policy=ToolPolicy()
        )
        return result.text

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    from typing import cast

    from chattice.adapters.google_chat import parse_interaction

    event = cast(
        MessageEvent,
        parse_interaction(
            {
                "type": "MESSAGE",
                "message": {"text": "привет"},
                "user": {"name": "users/1"},
                "space": {"name": "spaces/A"},
            }
        ),
    )
    result = await dispatcher.feed_update(event, backend=agent)
    assert result == "echo: привет"


class _FakeGenAIClient:
    """Records generate_content calls; no network."""

    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.calls: list[tuple[str, object, object]] = []

    class aio:
        pass


def _fake_response(reply_text: str) -> object:
    class _Part:
        text = reply_text

    class _Content:
        parts: list[object] = [_Part()]  # noqa: RUF012 — test stub

    class _Candidate:
        content = _Content()

    class _Response:
        candidates: list[object] = [_Candidate()]  # noqa: RUF012 — test stub

    return _Response()


async def test_gemini_adapter_bridges_text(monkeypatch: object) -> None:
    from chattice.experimental.ai.google import GeminiAgentBackend

    backend = GeminiAgentBackend(model="gemini-test")
    # inject a fake client via object state (dataclass frozen -> replace)
    import dataclasses

    calls: list[dict[str, object]] = []

    class _Aio:
        class models:
            @staticmethod
            async def generate_content(
                *, model: str, contents: object, config: object, **kwargs: object
            ) -> object:
                calls.append({"model": model, "config": config, **kwargs})
                return _fake_response("привет!")

    class _FakeClient:
        aio = _Aio()

    backend = dataclasses.replace(backend, client=_FakeClient())
    response = await backend.run(
        AgentRequest(text="ping"), tool_policy=ToolPolicy(), timeout=30.0
    )
    assert response.text == "привет!"
    assert calls and calls[0]["model"] == "gemini-test"
    # timeout now travels in config.http_options (milliseconds)
    assert cast(Any, calls[0]["config"]).http_options.timeout == 30000


async def test_gemini_tool_policy_filters_declarations(monkeypatch: object) -> None:
    import dataclasses

    from chattice.experimental.ai.google import GeminiAgentBackend

    calls: list[dict[str, object]] = []

    class _Aio:
        class models:
            @staticmethod
            async def generate_content(
                *, model: str, contents: object, config: object, **kwargs: object
            ) -> object:
                calls.append({"config": config})
                return _fake_response("ok")

    class _FakeClient:
        aio = _Aio()

    backend = dataclasses.replace(
        GeminiAgentBackend(
            model="m",
            tool_declarations=[{"name": "search"}, {"name": "write_db"}],
        ),
        client=_FakeClient(),
    )
    await backend.run(
        AgentRequest(text="q"),
        tool_policy=ToolPolicy(allowed_tools=frozenset({"search"})),
    )
    config = cast(Any, calls[0]["config"])
    assert config.tools is not None
    assert len(config.tools[0].function_declarations) == 1
    assert config.tools[0].function_declarations[0].name == "search"


async def test_gemini_read_only_default_blocks_tools(monkeypatch: object) -> None:
    import dataclasses

    from chattice.experimental.ai.google import GeminiAgentBackend

    calls: list[dict[str, object]] = []

    class _Aio:
        class models:
            @staticmethod
            async def generate_content(
                *, model: str, contents: object, config: object, **kwargs: object
            ) -> object:
                calls.append({"config": config})
                return _fake_response("ok")

    class _FakeClient:
        aio = _Aio()

    backend = dataclasses.replace(
        GeminiAgentBackend(model="m", tool_declarations=[{"name": "search"}]),
        client=_FakeClient(),
    )
    await backend.run(AgentRequest(text="q"), tool_policy=ToolPolicy())
    assert cast(Any, calls[0]["config"]).tools is None


async def test_gemini_generation_kwargs_cannot_smuggle_tools() -> None:
    """A2 regression: tools/tool_config cannot bypass ToolPolicy."""
    import pytest

    from chattice.experimental.ai.google import GeminiAgentBackend

    with pytest.raises(ValueError, match="ToolPolicy"):
        GeminiAgentBackend(model="m", generation_kwargs={"tools": [{"name": "x"}]})
    with pytest.raises(ValueError, match="ToolPolicy"):
        GeminiAgentBackend(
            model="m", generation_kwargs={"automatic_function_calling": True}
        )


async def test_write_tools_dropped_without_allow_writes() -> None:
    import dataclasses
    from typing import Any, cast

    from chattice.experimental.ai.google import GeminiAgentBackend

    calls: list[dict[str, object]] = []

    class _Aio:
        class models:
            @staticmethod
            async def generate_content(
                *, model: str, contents: object, config: object, **kwargs: object
            ) -> object:
                calls.append({"config": config})
                return _fake_response("ok")

    class _FakeClient:
        aio = _Aio()

    backend = dataclasses.replace(
        GeminiAgentBackend(
            model="m",
            tool_declarations=[{"name": "search"}, {"name": "write_db"}],
        ),
        client=_FakeClient(),
    )
    await backend.run(
        AgentRequest(text="q"),
        tool_policy=ToolPolicy(
            allowed_tools=frozenset({"search", "write_db"}),
            write_tools=frozenset({"write_db"}),
            allow_writes=False,
        ),
    )
    config = cast(Any, calls[0]["config"])
    names = [t.name for t in config.tools[0].function_declarations]
    assert names == ["search"]


def test_tool_policy_effective_tools() -> None:
    policy = ToolPolicy(
        allowed_tools=frozenset({"read", "write"}),
        write_tools=frozenset({"write"}),
        allow_writes=False,
    )
    assert policy.effective_tools() == frozenset({"read"})
    explicit = ToolPolicy(
        allowed_tools=frozenset({"read", "write"}),
        write_tools=frozenset({"write"}),
        allow_writes=True,
    )
    assert explicit.effective_tools() == frozenset({"read", "write"})
