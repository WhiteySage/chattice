# ruff: noqa: ASYNC109 — timeout kwarg is part of the bridge contract
"""Small agent-bridging contracts (Phase 20).

Design rules:
- Chat context travels IN, plain text OUT. The framework never defines
  Gemini/ADK-specific event types or tool schemas in core.
- Execution concerns (deadlines, cancellation, backpressure, tool
  authorization, audit) are the BACKEND's contract: `run()` accepts a
  timeout and ToolPolicy describes an allowlist — no policy engine here.
- A session is an opaque per-user/per-space identity + app data; storage
  is a tiny protocol with a Memory implementation. Provider memory
  belongs to the backend.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from chattice.events import SpaceRef, ThreadRef, UserRef

__all__ = [
    "AgentBackend",
    "AgentContext",
    "AgentRequest",
    "AgentResponse",
    "AgentSession",
    "AgentSessionStorage",
    "FakeAgent",
    "MemoryAgentSessionStorage",
    "ToolPolicy",
]


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Google Chat identity for an agent request."""

    user: UserRef | None = None
    space: SpaceRef | None = None
    thread: ThreadRef | None = None


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """One message for the backend, with Chat context and app data."""

    text: str
    context: AgentContext = field(default_factory=AgentContext)
    data: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_event(cls, event: object) -> AgentRequest:
        """Build a request from a Chattice message event (typed fields only)."""
        from chattice.events import MessageEvent

        if isinstance(event, MessageEvent):
            return cls(
                text=event.text,
                context=AgentContext(
                    user=event.actor,
                    space=event.space,
                    thread=event.thread,
                ),
            )
        raise TypeError(f"cannot build AgentRequest from {type(event).__name__}")


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Plain-text answer. Text is the ONLY cross-provider contract."""

    text: str
    done: bool = True


@dataclass(frozen=True, slots=True)
class AgentSession:
    """Opaque session identity + application-owned data."""

    session_id: str
    data: Mapping[str, object] = field(default_factory=dict)


class AgentSessionStorage(Protocol):
    """Small session-association contract (Memory implementation ships)."""

    async def get_session(self, key: str) -> AgentSession | None: ...

    async def save_session(self, key: str, session: AgentSession) -> None: ...


class MemoryAgentSessionStorage:
    """In-process session storage (tests and development)."""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    async def get_session(self, key: str) -> AgentSession | None:
        return self._sessions.get(key)

    async def save_session(self, key: str, session: AgentSession) -> None:
        self._sessions[key] = session


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Allowlist-based tool authorization for provider tool use.

    Defaults to read-only-empty (no tools). ``write_tools`` classifies
    which allowlisted tools are WRITES: they are dropped unless
    ``allow_writes`` is True (explicit opt-in). CONFIRMATION for actual
    write execution is application responsibility — the policy only
    gates what may be offered to the model.
    """

    allowed_tools: frozenset[str] = frozenset()
    write_tools: frozenset[str] = frozenset()
    allow_writes: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_tools", frozenset(self.allowed_tools))
        object.__setattr__(self, "write_tools", frozenset(self.write_tools))

    def effective_tools(self) -> frozenset[str]:
        """Tools that may actually be offered under this policy."""
        tools = self.allowed_tools
        if not self.allow_writes:
            tools = tools - self.write_tools
        return tools


class AgentBackend(Protocol):
    """The bridge contract: Chat context in, plain text out."""

    async def run(
        self,
        request: AgentRequest,
        *,
        session: AgentSession | None = None,
        tool_policy: ToolPolicy | None = None,
        timeout: float | None = None,
    ) -> AgentResponse: ...


class FakeAgent:
    """Deterministic test backend (echo/canned replies, call recording)."""

    def __init__(self, replies: Sequence[str] | None = None) -> None:
        self.replies = list(replies) if replies is not None else []
        self.requests: list[AgentRequest] = []
        self._index = 0

    async def run(
        self,
        request: AgentRequest,
        *,
        session: AgentSession | None = None,
        tool_policy: ToolPolicy | None = None,
        timeout: float | None = None,
    ) -> AgentResponse:
        self.requests.append(request)
        if self.replies:
            text = self.replies[min(self._index, len(self.replies) - 1)]
            self._index += 1
            return AgentResponse(text=text)
        return AgentResponse(text=f"echo: {request.text}")
