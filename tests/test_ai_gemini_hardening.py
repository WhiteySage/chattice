"""F05 regression: frozen Gemini policy inputs and owned provider resources."""

from __future__ import annotations

import dataclasses
from typing import Any, cast

import pytest

from chattice.experimental.ai import AgentRequest, ToolPolicy
from chattice.experimental.ai.google import GeminiAgentBackend


def _fake_response(reply_text: str = "ok") -> object:
    class _Part:
        text = reply_text

    class _Content:
        parts: list[object] = [_Part()]  # noqa: RUF012 — test stub

    class _Candidate:
        content = _Content()

    class _Response:
        candidates: list[object] = [_Candidate()]  # noqa: RUF012 — test stub

    return _Response()


class _FakeModels:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        self.calls = calls

    async def generate_content(
        self, *, model: str, contents: object, config: object, **kwargs: object
    ) -> object:
        self.calls.append({"config": config})
        return _fake_response()


class _FakeClient:
    def __init__(self, calls: list[dict[str, object]]) -> None:
        models = _FakeModels(calls)

        class _Aio:
            pass

        aio = _Aio()
        aio.models = models  # type: ignore[attr-defined]
        self.aio = aio


def _backend(**kwargs: Any) -> GeminiAgentBackend:
    return GeminiAgentBackend(model="m", **kwargs)


async def test_mutation_after_construction_cannot_add_forbidden_keys() -> None:
    """The audit's probe: mutating the caller's mapping after construction
    must NOT inject tools/tool_config/automatic_function_calling."""
    calls: list[dict[str, object]] = []
    kwargs: dict[str, object] = {"temperature": 0.5}
    backend = dataclasses.replace(
        _backend(generation_kwargs=kwargs), client=_FakeClient(calls)
    )
    kwargs["tools"] = [{"name": "search"}]  # caller mutates AFTER construction
    await backend.run(AgentRequest(text="q"), tool_policy=ToolPolicy())
    config = cast(Any, calls[0]["config"])
    assert getattr(config, "tools", None) is None
    assert "tools" not in backend.generation_kwargs


async def test_nested_tool_declarations_are_deep_copied() -> None:
    calls: list[dict[str, object]] = []
    declaration: dict[str, object] = {
        "name": "search",
        "parameters": {"type": "OBJECT", "properties": {"q": {"type": "STRING"}}},
    }
    backend = dataclasses.replace(
        _backend(tool_declarations=[declaration]), client=_FakeClient(calls)
    )
    cast(Any, declaration["parameters"])["properties"]["q"]["type"] = "EVIL"
    await backend.run(
        AgentRequest(text="q"),
        tool_policy=ToolPolicy(allowed_tools=frozenset({"search"})),
    )
    config = cast(Any, calls[0]["config"])
    tools = config.tools[0].function_declarations
    assert tools[0].parameters.properties["q"].type == "STRING"


def test_duplicate_tool_names_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _backend(tool_declarations=[{"name": "a"}, {"name": "a"}])


def test_nameless_tool_declaration_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _backend(tool_declarations=[{"description": "no name"}])


def test_non_mapping_tool_declaration_rejected() -> None:
    with pytest.raises(ValueError, match="mappings"):
        _backend(tool_declarations=["search"])


def test_non_json_generation_kwargs_rejected() -> None:
    with pytest.raises(TypeError, match="JSON-like"):
        _backend(generation_kwargs={"callback": lambda: None})


async def test_defense_in_depth_re_filter_at_provider_boundary() -> None:
    """Even if an internal layer forcibly rewrites the frozen mapping,
    run() re-filters forbidden keys at the final boundary."""
    calls: list[dict[str, object]] = []
    backend = dataclasses.replace(_backend(), client=_FakeClient(calls))
    object.__setattr__(backend, "generation_kwargs", {"tools": [{"name": "search"}]})
    await backend.run(AgentRequest(text="q"), tool_policy=ToolPolicy())
    config = cast(Any, calls[0]["config"])
    assert getattr(config, "tools", None) is None


class _CountingFactory:
    def __init__(self, close_calls: list[str]) -> None:
        self.close_calls = close_calls
        self.created = 0

    def __call__(self) -> Any:
        self.created += 1
        owner_close_calls = self.close_calls

        class _Owned:
            aio = _FakeModels([])

            def close(self) -> None:
                owner_close_calls.append("owned")

        return _Owned()


async def test_owned_client_created_once_and_closed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google.genai

    close_calls: list[str] = []
    factory = _CountingFactory(close_calls)
    monkeypatch.setattr(google.genai, "Client", factory)
    backend = _backend()
    assert backend._client() is backend._client()  # cached, single creation
    assert factory.created == 1
    await backend.aclose()
    await backend.aclose()  # idempotent
    assert close_calls == ["owned"]


async def test_injected_client_never_closed() -> None:
    close_calls: list[str] = []
    injected = _CountingFactory(close_calls)()
    backend = dataclasses.replace(_backend(client=injected))
    await backend.aclose()
    assert close_calls == []  # injected clients are caller-owned


async def test_run_after_close_raises() -> None:
    calls: list[dict[str, object]] = []
    backend = dataclasses.replace(_backend(), client=_FakeClient(calls))
    await backend.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        await backend.run(AgentRequest(text="q"))
    assert calls == []  # no provider call after close
