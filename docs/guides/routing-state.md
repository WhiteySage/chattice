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
