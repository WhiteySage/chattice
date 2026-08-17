# ruff: noqa: ASYNC109 — timeout kwarg is part of the bridge contract
"""Thin Gemini adapter over AgentBackend (optional extra `chattice[gemini]`).

Phase 21 rule: the adapter bridges Chat context to google-genai and
NOTHING more — no session semantics, no tool engines, no memory.
The provider SDK is imported lazily so `import chattice.experimental.ai` never
requires the extra.

The backend is constructed with the client OR the SDK is created from
env defaults; model name and system instruction are explicit. Tool
declarations passed at construction are filtered per request by
ToolPolicy.allowed_tools; a tool never declared cannot run.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from chattice.experimental.ai import AgentRequest, AgentResponse, ToolPolicy

__all__ = ["GeminiAgentBackend"]


_FORBIDDEN_GENERATION_KWARGS = frozenset(
    {"tools", "tool_config", "automatic_function_calling"}
)


def _freeze_json(value: object, *, where: str) -> object:
    """Deep-copy a value into immutable JSON-like data.

    A frozen dataclass must not retain caller-owned mutable graphs:
    mappings and sequences are rebuilt recursively; enums are reduced
    to their JSON-compatible values; anything else is rejected at
    construction.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return _freeze_json(value.value, where=where)
    if isinstance(value, Mapping):
        return {
            str(key): _freeze_json(item, where=where) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_freeze_json(item, where=where) for item in value]
    raise TypeError(
        f"{where} must be JSON-like (str/int/float/bool/None/list/dict); "
        f"got {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True)
class GeminiAgentBackend:
    """Google-genai-backed AgentBackend (thin; provider does the work).

    Tool configuration is constructed SOLELY from the per-request
    ToolPolicy: smuggling `tools`/`tool_config`/automatic-function-calling
    through `generation_kwargs` raises at construction (A2 — the policy
    would otherwise be bypassable), and the forbidden keys are re-filtered
    at the final provider boundary as defense in depth. When tools
    are enabled, the tool declarations also LEAVE the application (they
    are sent to the provider). The timeout travels in
    `config.http_options.timeout` (milliseconds) per the official SDK
    configuration model.

    Configuration inputs are deep-copied into immutable JSON-like
    values at construction — mutating the caller's mappings afterwards
    cannot change the backend. An OWNED provider client (created when
    ``client=`` is None) is cached and closed via ``close()``/``aclose()``;
    an INJECTED client is never closed by the backend.
    """

    model: str
    system_instruction: str | None = None
    client: Any = None  # google.genai.Client; owned-lazy when None
    tool_declarations: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    generation_kwargs: Mapping[str, object] = field(default_factory=dict)
    _owned_client: Any = field(default=None, init=False, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        generation_kwargs = cast(
            dict[str, object],
            _freeze_json(self.generation_kwargs, where="generation_kwargs"),
        )
        tool_declarations = cast(
            list[object],
            _freeze_json(self.tool_declarations, where="tool_declarations"),
        )
        forbidden = _FORBIDDEN_GENERATION_KWARGS & set(generation_kwargs)
        if forbidden:
            raise ValueError(
                f"generation_kwargs may not set {sorted(forbidden)}: tool "
                "configuration belongs to ToolPolicy only"
            )
        names: list[str] = []
        for declaration in tool_declarations:
            if not isinstance(declaration, Mapping):
                raise ValueError(
                    "tool declarations must be mappings with a string 'name'"
                )
            name = declaration.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    "tool declarations must be mappings with a non-empty string 'name'"
                )
            names.append(name)
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate tool declaration names: {names}")
        object.__setattr__(self, "generation_kwargs", generation_kwargs)
        object.__setattr__(self, "tool_declarations", tuple(tool_declarations))

    def _client(self) -> Any:
        if self.client is not None:
            return self.client
        owned = self._owned_client
        if owned is not None:
            return owned
        try:
            from google import genai
        except ImportError as error:  # pragma: no cover - env-dependent
            raise ImportError(
                "GeminiAgentBackend requires the `chattice[gemini]` extra "
                "(google-genai)"
            ) from error
        created = genai.Client()
        object.__setattr__(self, "_owned_client", created)
        return created

    async def aclose(self) -> None:
        """Close the backend-OWNED provider client (idempotent).

        An injected client is never closed. After close, ``run()`` raises.
        """
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        owned = self._owned_client
        if owned is None:
            return
        closer = getattr(owned, "close", None) or getattr(owned, "aclose", None)
        if closer is None:
            return
        result = closer()
        if inspect.isawaitable(result):
            await result

    def close(self) -> None:
        """Synchronous variant for sync-typed provider clients.

        An aio client's closer is awaitable and cannot run here — use
        ``aclose()`` instead.
        """
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        owned = self._owned_client
        if owned is None:
            return
        closer = getattr(owned, "close", None)
        if closer is None:
            return
        result = closer()
        if inspect.isawaitable(result):
            raise RuntimeError(
                "the owned provider client has an async closer — use aclose()"
            )

    def _filtered_tools(
        self, policy: ToolPolicy | None
    ) -> list[Mapping[str, object]] | None:
        if not self.tool_declarations:
            return None
        if policy is None:
            return None  # read-only default: NO tools run
        allowed = policy.effective_tools()
        if not allowed:
            return None
        filtered = [
            declaration
            for declaration in self.tool_declarations
            if declaration.get("name") in allowed
        ]
        return filtered or None

    async def run(
        self,
        request: AgentRequest,
        *,
        session: object = None,
        tool_policy: ToolPolicy | None = None,
        timeout: float | None = None,
    ) -> AgentResponse:
        if self._closed:
            raise RuntimeError("GeminiAgentBackend is closed")
        client = self._client()
        try:
            from google.genai import types
        except ImportError as error:  # pragma: no cover - env-dependent
            raise ImportError(
                "GeminiAgentBackend requires the `chattice[gemini]` extra "
                "(google-genai)"
            ) from error

        contents = types.Content(
            role="user", parts=[types.Part.from_text(text=request.text)]
        )
        config_kwargs: dict[str, Any] = dict(self.generation_kwargs)
        # Defense in depth: re-filter the forbidden keys at the final
        # provider boundary — even a compromised intermediate layer cannot
        # smuggle tool control past the policy.
        for key in _FORBIDDEN_GENERATION_KWARGS:
            config_kwargs.pop(key, None)
        if self.system_instruction is not None:
            config_kwargs["system_instruction"] = self.system_instruction
        tools = self._filtered_tools(tool_policy)
        if tools is not None:
            config_kwargs["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(**t)  # type: ignore[arg-type]
                        for t in tools
                    ]
                )
            ]
            # NO automatic function execution: there is no audited
            # execution contract in this adapter.
            config_kwargs["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
        if timeout is not None:
            config_kwargs["http_options"] = types.HttpOptions(
                timeout=max(1, int(timeout * 1000))
            )
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        text = "".join(
            part.text for part in response.candidates[0].content.parts if part.text
        )
        return AgentResponse(text=text)
