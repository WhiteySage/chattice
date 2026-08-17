# Cookbook

Recipes demonstrate composition. They do not add business objects to core.

## Poll

Build a poll from a `Card`, `SelectionInput` or Buttons, a named
`ActionEvent`, and application storage. Use FSM only if the poll workflow must
survive additional interactions; store votes in domain storage. There is no
`Poll` class in Chattice.

## Approval

Build an approval from a request `FormModel`, a public Card with approve/reject
buttons, typed `ActionData` carrying the request identifier, a Thread for the
audit conversation, and revisioned application/FSM storage. Authorization to
approve is application policy, never inferred from a card parameter.

```python
from dataclasses import dataclass

from chattice.actions import ActionData


@dataclass
class ApprovalAction(ActionData, function="approval.decide"):
    request_id: str
    decision: str
```

Bind the instance to a button with `Button(..., action=ApprovalAction(...))`
and route it with `ApprovalAction.filter()`. Re-fetch the request and authorize
the actor before mutating anything.

## Incident workflow

Use a Space and Thread for collaboration, a Card for status, Actions for
transitions, `Bot.update_message` for the status card, Workspace Events for
resource-change observation, and application storage for incident data. Pins
are a Google Developer Preview surface and require explicit eligibility,
scopes, and raw/preview handling.

## AI assistant

AI is an integration story. Stable Chattice owns the selected Message/Thread,
the message action, state, cards, dialogs, DI, and auth boundary. The
application owns the model/provider, prompt, RAG, tools, safety policy, user
notice, authorization, and cost controls.

```python
from chattice.experimental.ai import AgentBackend, AgentRequest, ToolPolicy


@router.message()
async def assistant(message: MessageEvent, agent: AgentBackend) -> str:
    result = await agent.run(
        AgentRequest.from_event(message),
        tool_policy=ToolPolicy(allowed_tools=frozenset({"search"})),
        timeout=20.0,
    )
    return result.text
```

Everything imported from `chattice.experimental.ai` is experimental. For work
that can exceed the HTTP deadline, return quickly and send the eventual result
through an authenticated `Bot`; use thread-scoped state where conversation
continuity matters. MCP, ADK, A2A, Dialogflow, and custom LLM providers belong
in integration-specific application modules.

See [stability](../stability.md) for the compatibility tiers.
