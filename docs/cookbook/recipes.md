# Cookbook

Recipes demonstrate composition. They do not add business objects to core.

## Local chart as a Chat attachment

Render a PNG with imgkit and send it using the explicit USER namespace
(requires `chattice[media]`, user credentials, imgkit, and its wkhtmltoimage
runtime; see [Files, Images & Media](../guides/files-media.md)). Render off the
event loop and keep the result in memory so concurrent requests do not share
an output filename:

```python
import asyncio

import imgkit
from chattice import F, Router
from chattice.client import Bot
from chattice.events import MessageEvent
from chattice.media import InputFile

router = Router()


@router.message(F.argument_text == "/report")
async def report(message: MessageEvent, bot: Bot) -> None:
    png = await asyncio.to_thread(
        imgkit.from_string,
        "<h1>Revenue</h1><p>Up 12%</p>",
        False,
        options={"format": "png"},
    )
    await bot.user.messages.create(
        message.space,
        thread=message.thread,
        attachments=[InputFile.from_bytes(png, filename="report.png")],
    )
```

Configure the handler's Bot with USER credentials. It sends the attachment
explicitly and returns `None`; a raw SDK Message is not a synchronous response
facade. Use an application background job if rendering may exceed the HTTP
interaction deadline.

PDF and arbitrary bytes work identically:

```python
# Attachment sends run on the USER identity end-to-end.
await bot.user.messages.create(
    "spaces/AAA",
    text="Report",
    attachments=[InputFile.from_path("report.pdf")],
)

await bot.user.messages.create(
    "spaces/AAA",
    attachments=[
        InputFile.from_bytes(
            png_bytes,
            filename="result.png",
            content_type="image/png",
        )
    ],
)
```

For a picture inside a Card, use `Image.from_url()` or configure an
`AssetPublisher` for `Image.from_path()` / `Image.from_bytes()`. The resulting
Card image URL must be publicly retrievable; local attachments remain a
separate USER-authenticated channel.

## Poll

Build a poll from a `Card`, `SelectionInput` or Buttons, a named
`ActionEvent`, and application storage. Use FSM only if the poll workflow must
survive additional interactions; store votes in domain storage. There is no
`Poll` class in Chattice.

## Approval

Build an approval from a request `FormModel`, a public Card with approve/reject
buttons, typed `ActionData` carrying the request identifier, a Thread for the
activity history, and revisioned application/FSM storage. Authorization to
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

## Reactions (user auth)

Google serves reactions with **user authentication**
(`chat.messages.reactions` / `chat.messages.reactions.readonly`), so
configure the Bot with a user identity (OAuth or DWD) before calling;
`bot.user.reactions` is the USER-only resource namespace.

```python
# Add a 🔥 reaction to a message (unicode emoji string).
await bot.user.reactions.create("spaces/SPACE/messages/MSG", emoji="🔥")

# List reactions on a message (explicit async pager).
pager = await bot.user.reactions.list("spaces/SPACE/messages/MSG", page_size=50)
async for reaction in pager:
    print(reaction.emoji.unicode)
```

## Incident workflow

Use a Space and Thread for collaboration, a Card for status, Actions for
transitions, `bot.app.messages.update` for the status card, Workspace Events for
resource-change observation, and application storage for incident data. Pins
are a Google Developer Preview surface and require explicit eligibility,
scopes, and raw/preview handling.

## AI assistant

AI is an integration story. Stable Chattice owns the selected Message/Thread,
the message action, state, cards, dialogs, DI, and auth boundary. The
application owns the model/provider, instructions, retrieval, tools, safety policy, user
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

`AgentRequest.from_event()` accepts `MessageEvent` only. For commands
and card buttons, build the request from the text you already have:

```python
# slash command: use the argument text
@router.command()
async def ask_cmd(event: CommandEvent, agent: AgentBackend) -> str:
    result = await agent.run(AgentRequest(text=event.message_text or ""))
    return result.text


# card button: use a field of your typed ActionData
@router.action("ai.ask", AskAction.filter())
async def ask_btn(event: ActionEvent, data: AskAction, agent: AgentBackend) -> str:
    result = await agent.run(AgentRequest(text=data.question))
    return result.text
```

Everything imported from `chattice.experimental.ai` is experimental. For work
that can exceed the HTTP deadline, return quickly and send the eventual result
through an authenticated `Bot`; use thread-scoped state where conversation
continuity matters. MCP, ADK, A2A, Dialogflow, and custom LLM providers belong
in integration-specific application modules.

See [stability](../stability.md) for the compatibility tiers.

### Private ticket form

`/create-ticket` → private card in the shared Space → Dialog → typed
form → update the ORIGINAL private message. Per-user state lives in
application storage keyed by `StorageKey(user, space, thread)`; the
private card is visible only to `privateMessageViewer`. See the
dialog section of `examples/docs/from_zero.py` for the
card/dialog mechanics.

### Shared card updates (two users)

One shared card in a Space, Assign/Approve buttons, `bot.app.messages.update`
on the ONE message resource; workflow state lives in the application DB,
NOT in per-user FSM. Per-user FSM keys never change how the shared
card renders.

### Error handler

Register an error observer to catch handler failures and answer the
user (or log) instead of surfacing a bare 500:

```python
from chattice import Dispatcher, Router
from chattice.events import ErrorEvent

router = Router()


@router.error()
async def on_error(event: ErrorEvent) -> str:
    # event.exception, event.event, event.error_type
    return "Something went wrong — try again."
```

### Idempotent sends

For retried outbound sends, pass a stable `request_id` (Google
deduplicates by it within the retention window) or a client-assigned
`message_id`:

```python
await bot.app.messages.create(
    "spaces/AAA",
    text="Deploy finished",
    request_id=f"deploy-{deployment.id}",
)
```
