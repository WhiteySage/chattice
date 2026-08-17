# FSM

Phase 7 adds a finite-state machine: `State`/`StatesGroup` workflow
definitions, a `FSMContext` injected per event, `StateFilter` routing, and two
storage backends (`MemoryStorage`, `RedisStorage`). See
[ADR-006](../adr/ADR-006-fsm-key-strategy.md) for the key-strategy decision.

## States

```python
from chattice.fsm import State, StatesGroup


class Incident(StatesGroup):
    title = State()
    severity = State()
    confirmation = State()
```

`StatesGroup` members get `"<GroupName>:<attr_name>"` string keys (here
`Incident:title`, `Incident:severity`, `Incident:confirmation`). A standalone
`State(state="custom:key")` can carry an explicit key. The string is what
storages persist and what `StateFilter` compares.

## StorageKey and strategies

The storage key is derived from **Google resource references, not Telegram
chat IDs** — the strings already normalized by the interaction adapter:
`event.actor.name` (`"users/..."`), `event.space.name` (`"spaces/..."`),
`event.thread.name` (`"spaces/.../threads/..."`).

```python
@dataclass(frozen=True, slots=True)
class StorageKey:
    user: str | None
    space: str | None
    thread: str | None
```

`StorageKey.build(event, strategy)` picks which dimensions are required:

| Strategy | Key dimensions | Fails when |
| --- | --- | --- |
| `USER_IN_SPACE` (default) | user + space (+ thread if present) | user or space ref missing |
| `USER` | user only | user ref missing |
| `SPACE` | space only | space ref missing |

The default is `USER_IN_SPACE`: state never leaks across spaces (the same
person in a DM and a group space has two independent workflows), and DM flows
are naturally isolated per user. `USER` is the opt-in for cross-space user
state; `SPACE` shares one workflow among everyone in a space.

When the key cannot be derived, `FSMContext` read helpers degrade gracefully
(`get_state()` → `None`, `get_data()` → `{}`) and mutating operations raise
`FSMError`.

## FSMContext: pre-injection contract

`Dispatcher(fsm_storage=..., fsm_strategy=...)` builds
`FSMContext(storage, StorageKey.build(event, strategy))` **before filter
evaluation** and exposes it as `data["state"]`. Handlers (and filters) receive
it through the existing name-based dependency injection:

```python
@router.message(StateFilter(Incident.title))
async def title(message: MessageEvent, state: FSMContext) -> str:
    await state.update_data(title=message.text)
    await state.set_state(Incident.severity)
    return "title-ok"
```

The injection is **additive**: a dispatcher constructed without
`fsm_storage` behaves exactly as before, and a handler that asks for `state`
fails with a dependency-resolution error rather than silently getting nothing.

Note: a `State` instance shared across multiple `StatesGroup`s is
rebranded to the last group that declares it — declare states once, per
group. When `fsm_storage` is configured, the injected `data["state"]`
takes precedence over a user-supplied `state=` kwarg in `feed_update`.

## StateFilter

`StateFilter(*states)` routes by the current state; it needs the pre-injected
context, so it only matches on a dispatcher configured with `fsm_storage`.
`StateFilter()` (no arguments) matches any non-`None` state; an event with no
state (or no derivable key) never matches. Filters run before handlers, so a
message outside the workflow falls through to unguarded handlers or is
ignored.

## Storage backends and honest concurrency

Both backends implement `BaseStorage` (async get/set state, get/set/update
data, finish) over a `StorageKey`.

- `MemoryStorage` — in-process, for development and tests. Per-key
  `asyncio.Lock`s serialize writes **within one event loop**; nothing survives
  across processes.
- `RedisStorage` (`chattice[redis]` extra) — `redis.asyncio` with a
  namespaced key layout (`chattice:fsm:<user>:<space>:<thread>:state|data`).
  Individual commands are atomic, and that is all that is promised:
  `update_data` is a GET → merge → SET under a **process-local** lock, so it
  is **not** cross-process safe, and there is no Lua scripting. Prefer
  `set_data` when replace semantics are acceptable.

Neither backend automatically serializes handlers for the same key — state
isolation and handler serialization are separate concerns.

## Complete workflow example

`examples/phase7.py` runs the full Incident flow through
`parse_interaction` + `feed_update` (no network), mirroring `tests/fsm/test_gate.py`:

```python
import asyncio

from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.events import MessageEvent
from chattice.fsm import FSMContext, MemoryStorage, StateFilter, StorageKey
from chattice.fsm.states import State, StatesGroup


class Incident(StatesGroup):
    title = State()
    severity = State()
    confirmation = State()


async def main() -> None:
    storage = MemoryStorage()
    router = Router()

    @router.message(StateFilter(Incident.title))
    async def title(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(title=message.text)
        await state.set_state(Incident.severity)
        return "title-ok"

    @router.message(StateFilter(Incident.severity))
    async def severity(message: MessageEvent, state: FSMContext) -> str:
        await state.update_data(severity=message.text)
        await state.set_state(Incident.confirmation)
        return "severity-ok"

    @router.message(StateFilter(Incident.confirmation))
    async def confirmation(message: MessageEvent, state: FSMContext) -> str:
        data = await state.get_data()
        await state.finish()
        return f"done: {data['title']} {data['severity']} {message.text}"

    dispatcher = Dispatcher(fsm_storage=storage)
    dispatcher.include_router(router)

    payload = {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": "Bug"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/A"},
    }
    # No state yet -> no StateFilter matches, returns None.
    print(await dispatcher.feed_update(parse_interaction(payload)))
    # Workflow starts outside the message stream (e.g. a slash command).
    await storage.set_state(
        StorageKey(user="users/1", space="spaces/A", thread=None),
        Incident.title.state,
    )
    print(
        await dispatcher.feed_update(
            parse_interaction({**payload, "message": {"text": "Bug"}})
        )
    )
    print(
        await dispatcher.feed_update(
            parse_interaction({**payload, "message": {"text": "high"}})
        )
    )
    print(
        await dispatcher.feed_update(
            parse_interaction({**payload, "message": {"text": "confirm"}})
        )
    )
    # finish() removed the record -> no matches again.


if __name__ == "__main__":
    asyncio.run(main())
```

The same workflow passes the CI gate on both `MemoryStorage` and
`RedisStorage` (fakeredis) — `tests/fsm/test_gate.py`.
