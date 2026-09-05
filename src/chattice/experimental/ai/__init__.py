"""Experimental AI bridging abstractions.

``chattice.experimental.ai`` is deliberately SMALL: it connects Google
Chat context to an agent backend. It is NOT a generic LLM framework, agent runtime, RAG
stack, or planner. Provider SDKs live in optional EXPERIMENTAL adapters
(``chattice.experimental.ai.google``). The entire namespace is
outside the stable core API and the base install never drags an AI stack.

Dependency direction (machine-enforced): experimental AI -> core; core
never imports experimental AI.
"""

from .models import (
    AgentBackend,
    AgentContext,
    AgentRequest,
    AgentResponse,
    AgentSession,
    AgentSessionStorage,
    FakeAgent,
    MemoryAgentSessionStorage,
    ToolPolicy,
)

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
