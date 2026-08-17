# Testing

`chattice.testing` is the framework's testing toolkit: mocks, typed event
builders, and assertions that let you exercise a whole application pipeline
without ever touching raw Google JSON or standing up network transports.
The core engine never imports `testing` — the dependency is one-way.

A CI gate (`tests/testing/test_gate.py`) pins the core contract: an
application handler is tested end-to-end with `MockBot` + `EventFactory`,
with **zero Google internals mocked**.

## Package contents

```text
chattice/testing/
├── MockBot           call-recording stand-in for the outgoing API
├── EventFactory      typed event builders (no raw Google JSON)
├── FakeChatTransport gapic-contract fake transport (migrated from
│                     tests/client; compat re-export kept)
├── assert_card_has_button / assert_card_header
└── set_state_for     FSM seeding helper
```

## The DI pattern: `feed_update(event, bot=mock_bot)`

Handlers receive dependencies by parameter name. Inject the `MockBot` the
same way a real app injects the `Bot` — via `feed_update` context:

```python
from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.testing import EventFactory, MockBot

bot = MockBot()
router = Router()


@router.message()
async def echo(message: MessageEvent, bot: MockBot) -> str:
    await bot.send_message(message.space, text=message.text)
    return "handled"


dispatcher = Dispatcher()
dispatcher.include_router(router)
result = await dispatcher.feed_update(EventFactory.message("ping"), bot=bot)
assert result == "handled"
bot.assert_message_sent("ping")
```

## MockBot

`MockBot` records every outgoing call (`send_message`, `update_message`,
`delete_message`, `get_message`, `get_space`) with its arguments in
`.calls` and fabricates SDK proto responses — no transport, no network.
`capabilities` mirrors a real app-authenticated Bot.

Assertions (each fails with an actionable message):

- `assert_message_sent(text: str | None = None, *, count: int = 1)` — the
  outgoing calls, optionally with an exact text and call count.
- `assert_no_messages()` — proves a handler sent nothing.
- `calls` — the raw `(kind, args)` list for advanced checks (e.g. asserting
  on `get_message` reads or `update_message` payloads).

`MockBot.send_message` mirrors the real `Bot` parameter names exactly —
DI resolves by keyword, so a mismatch fails the CI gate, never the
handler.

## EventFactory

`EventFactory` builds frozen domain events directly from their typed
constructors — unit tests never paste raw Google JSON:

- `message(text, *, user=None, space=None, thread=None, event_time=None)`
- `action(name, parameters=None, *, form_inputs=None, dialog=None, ...)`
- `added_to_space(...)`, `removed_from_space(...)`, `app_home(...)`,
  `form_submit(function_name, ...)`
- `workspace_event(cloud_type, *, event_id="evt-test", ...)`
- `unknown_event(original_type, ...)`

`user`/`space` accept either a typed reference or a Google resource-name
string (`"users/alice"`); `None` uses test defaults (`users/test`,
`spaces/test`).

## Card assertions

```python
from chattice.cards import Button, ButtonList, Card, Section
from chattice.testing import assert_card_has_button, assert_card_header

card = Card(
    sections=[
        Section(
            widgets=[ButtonList(buttons=[Button("Deploy", action="deploy.confirm")])]
        )
    ]
)
assert_card_has_button(card, action="deploy.confirm", text="Deploy")
assert_card_header(card, title="Pipeline")
```

`assert_card_has_button(card, *, action=None, text=None)` and
`assert_card_header(card, *, title=None, subtitle=None)` search the card
and raise with the missing match described.

## FSM seeding

Seed a workflow state for a test with `set_state_for(storage, key, state)`,
then route through the dispatcher as usual:

```python
from chattice.fsm import MemoryStorage, StorageKey, State, StatesGroup
from chattice.testing import set_state_for


class Flow(StatesGroup):
    start = State()
    waiting = State()


storage = MemoryStorage()
key = StorageKey(user="users/test", space="spaces/test", thread=None)
await set_state_for(storage, key, Flow.waiting)  # the StateFilter now matches
```

## Live integration suite

`tests/integration/live` exercises real Google Chat infrastructure and is
**skipped by default** — run it only with real credentials:

```bash
export CHATTICE_GOOGLE_CREDENTIALS=/path/to/service-account.json
pytest tests/integration/live -m google_live
```

Without credentials the suite reports 2 skipped (the network calls) — the
honest, expected state; the three contract tests (card round-trip,
command payloads, Workspace Pub/Sub replay) execute without network.
Setup, in short: a GCP project with the Google Chat API enabled, a
service-account JSON key, a Chat app set to **Live** with its membership
in a test space, and the `CHATTICE_GOOGLE_CREDENTIALS` +
`CHATTICE_GOOGLE_SPACE` env vars. The network bodies call the real API
and nothing fakes success — a green live run always means real
credentials were used.

## Runnable pytest example

```python
# tests/test_echo.py
import pytest

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.testing import EventFactory, MockBot


@pytest.fixture
def dispatcher() -> Dispatcher:
    router = Router()

    @router.message()
    async def echo(message: MessageEvent) -> str:
        return f"You said: {message.text}"

    dp = Dispatcher()
    dp.include_router(router)
    return dp


@pytest.fixture
def bot() -> MockBot:
    return MockBot()


@pytest.mark.asyncio
async def test_echo(dispatcher: Dispatcher, bot: MockBot) -> None:
    result = await dispatcher.feed_update(EventFactory.message("ping"), bot=bot)
    assert result == "You said: ping"
    bot.assert_no_messages()
```

Add `pytest-asyncio` to the dev dependencies; `asyncio_mode = "auto"`
is already configured in the project, so the `@pytest.mark.asyncio`
decorator is optional there.

