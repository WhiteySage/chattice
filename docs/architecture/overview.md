# Architecture overview

Status: **Implemented**.

## Current boundary

```text
decoded Google Mapping or synthetic Event
          |
          v (Google payload only)
 envelope normalization -> boundary validation -> domain Event
          |
          v
      Dispatcher
          |
          v
 Router tree -> specific Observer -> generic event fallback
          |
          v
 filters -> middleware -> dependency plan -> async handler
```

The engine is async-first, typed, deterministic, and transport-neutral. A pure
Google Chat interaction parser precedes it when applications have decoded
JSON. Optional packages add HTTP/FastAPI and Pub/Sub ingress, the asynchronous
Chat API client, Cards, authentication, FSM, storage, and testing helpers.

## Implemented package layout

```text
src/chattice/
├── __init__.py             # Dispatcher, Router, F
├── adapters/google_chat/   # pure envelope validation and normalization
├── auth/                   # application and delegated-user credentials
├── cards/                  # typed Cards v2 builders
├── client/                 # asynchronous Google Chat API client
├── events/                 # immutable synthetic/normalized domain events
├── dispatcher/             # dispatcher, router, observer, handler plans
├── filters/                # custom-filter contract and magic expressions
├── fsm/                    # workflow state and storage contracts
├── integrations/           # FastAPI and optional service integrations
├── testing/                # fakes, factories, and assertions
├── transports/             # HTTP and Pub/Sub ingress
├── workspace_events/       # independent Workspace Events runtime
├── middleware.py           # middleware protocol and base class
└── exceptions/             # failures and routing control primitives
```

## Public example

```python
from chattice import Dispatcher, F, Router
from chattice.events import ActionEvent, MessageEvent

router = Router(name="deployment")


@router.message(F.text == "ping")
async def ping(message: MessageEvent) -> str:
    return "pong"


@router.action("deploy.confirm")
async def confirm(action: ActionEvent) -> str:
    return action.name


dispatcher = Dispatcher()
dispatcher.include_router(router)

result = await dispatcher.feed_update(MessageEvent(text="ping"))
```

For external interaction JSON, call
`chattice.adapters.google_chat.parse_interaction(payload)` first.
`feed_update()` accepts only framework `Event` objects and returns the selected
handler or middleware result unchanged. The routing engine performs no network
I/O itself; invoked handlers, middleware, storage, and hooks may do so.

## Invariants

- Specific observers are exhausted across the router tree before the generic
  `event` fallback begins.
- First successfully invoked matching handler wins; dispatch never broadcasts.
- Router trees are acyclic and single-parent.
- Middleware runs after a candidate's filters pass.
- Signature plans are cached; invocation values are not.
- `None` is a valid handled result and is distinct internally from no match.
- Ordinary unhandled exceptions retain identity and propagate.
- Routing performs no Google or transport work.
- Handlers receive domain events; the original Google envelope remains
  explicitly accessible through `event.raw`.
- Raw interaction snapshots preserve the complete original envelope.

## Component boundaries

- Adapters normalize external payloads into framework-owned events.
- Dispatch, filters, middleware, and dependency injection perform no network
  calls by themselves.
- Transports verify and decode ingress before dispatch.
- The client owns outbound Google Chat API calls and credential selection.
- Cards and domain values remain independent of application storage.
- Workspace Events use a separate router and dispatcher because their delivery
  and response semantics differ from Chat interactions.
