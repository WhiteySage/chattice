# Architecture overview

Status: **Phase 2 interaction adapter implemented**.

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
Google Chat interaction parser now precedes it when applications have decoded
JSON. There is still no network client, credentials, HTTP server, FastAPI or
Starlette integration, Cards/response builder, or FSM.

## Implemented package layout

```text
src/chattice/
├── __init__.py             # Dispatcher, Router, F
├── adapters/google_chat/   # pure envelope validation and normalization
├── events/                 # immutable synthetic/normalized domain events
├── dispatcher/             # dispatcher, router, observer, handler plans
├── filters/                # custom-filter contract and magic expressions
├── middleware.py           # middleware protocol and base class
└── exceptions/             # failures and routing control primitives
```

Future packages are introduced only when their implementation phase begins.

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
`feed_update()` still accepts only framework `Event` objects, performs no I/O,
and returns the selected handler or middleware result unchanged.

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
- Google dictionaries stop at the adapter and never enter ordinary handlers.
- Raw interaction snapshots preserve the complete original envelope.

## Phase boundaries

- Phase 1: implemented synthetic events and core dispatch engine.
- Phase 2: implemented documented Google interaction fixtures and a pure
  parser/adapter into focused domain events.
- Phase 3: request verification and ASGI integrations.
- Phase 4: official asynchronous Chat API wrapper.
- Phase 5+: Cards, FSM, dialogs/App Home, and Pub/Sub in their defined phases.
