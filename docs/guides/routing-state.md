# Routing, dependency injection, and state

## Routers and filters

Create feature routers, then include each detached router exactly once:

```python
from chattice import Dispatcher, F, Router
from chattice.events import MessageEvent

support = Router(name="support")


@support.message(F.text == "help")
async def help_message(message: MessageEvent) -> str:
    return "How can I help?"


dispatcher = Dispatcher()
dispatcher.include_router(support)
```

Specific observers run before the generic `event` observer. Filters are
ordered and can inject mappings into handler dependency context. Middleware
runs outer-to-inner through the router tree. Error observers receive an
`ErrorEvent` and can translate application failures.

### Native regex routing

`F.text.regexp(...)` matches a string field with a Python regular
expression, `re.match` semantics (the pattern must match from the START
of the value). This is Python regex syntax — do not wrap patterns in
`/.../`.

```python
import re


@support.message(F.text.regexp(r"^[Тт]ест$"))
async def test_command(message: MessageEvent) -> str:
    return "ok"


@support.message(F.text.regexp(r"^тест$", flags=re.IGNORECASE))
async def test_command_ci(message: MessageEvent) -> str:
    return "ok"
```

A pattern string is compiled once at filter construction; invalid
patterns raise `ValueError` immediately, never at evaluation time.
Pre-compiled `re.Pattern` values are accepted as-is (and cannot be
combined with `flags`). Missing fields and non-string values never
match. String equality stays literal: `F.text == "^тест$"` compares the
exact characters, regex semantics never leak into `==`.

`F.text.regexp(...)` composes with `&`, `|`, `~` like any other Magic
Filter, e.g. `F.text.regexp(r"^ping") & ~F.text.regexp(r"pong$")`.

## Dependency injection

Handlers declare only the values they need. Event parameters are resolved by
type; application dependencies are resolved by name from dispatcher context:

```python
@router.message()
async def handle(message: MessageEvent, inventory: InventoryService) -> str:
    return await inventory.lookup(message.text)


result = await dispatcher.feed_update(event, inventory=inventory_service)
```

Define annotated handlers and injected classes at module scope so runtime type
hint resolution remains reliable.

## FSM scope

`StorageKey(user, space, thread)` is the complete key shape. There is no
`THREAD_USER` symbol. Strategies select dimensions from that key:

| Strategy | Scope |
| --- | --- |
| `USER_IN_SPACE` | user + Space, including Thread when present (default) |
| `USER` | user across Spaces |
| `SPACE` | shared Space state |

```python
from chattice.fsm import FSMContext, MemoryStorage, State, StateFilter, StatesGroup


class Flow(StatesGroup):
    waiting = State()


@router.message(StateFilter(Flow.waiting))
async def waiting(message: MessageEvent, state: FSMContext) -> str:
    await state.update_data(answer=message.text)
    await state.finish()
    return "Saved"


dispatcher = Dispatcher(fsm_storage=MemoryStorage())
```

Use `MemoryStorage` only within one development/test process. Use the Redis
backend or the revisioned `FSMRecordStorage` contract when state must survive
processes; compare-and-set is the concurrency boundary.

Next: [Workspace Events](workspace-events.md).

## Per-user FSM vs shared-resource state

FSM records scope per-user workflow state (USER / SPACE_USER / THREAD /
SPACE keys). For state that is SHARED across participants — a workflow
board, a shared card's votes, a team approval record — use your
application database keyed by the resource, not FSM. Per-user FSM never
changes how a shared Message renders; it only scopes each actor's
backend state.

