# Messages and Threads

## Receive and reply

```python
from chattice import Dispatcher, Router
from chattice.events import MessageEvent

router = Router()


@router.message()
async def echo(message: MessageEvent) -> str:
    return f"You said: {message.text}"


dispatcher = Dispatcher()
dispatcher.include_router(router)
```

A returned string is an immediate interaction response. Use
`message.argument_text` when routing Space mentions: Google provides the
mention-stripped body, which can still include surrounding whitespace.

## Contextual Chat API sends

Bind an authenticated Bot once:

```python
dispatcher = Dispatcher(bot=bot)


@router.message()
async def send_variants(message: MessageEvent) -> str:
    await message.reply("reply or fail if the incoming thread is gone")
    assert message.thread is not None
    await message.thread.send("continue the known thread")
    assert message.space is not None
    await message.space.send("start at the Space top level")
    return "sent"
```

`message.reply()` defaults to `MessageReplyOption.REPLY_OR_FAIL`. Generic
`thread.send()` / `space.send()` default to Google's fallback-to-new-thread
behavior unless you pass another `MessageReplyOption`.

## Imperative send

```python
from chattice.client import Bot, MessageReplyOption
from chattice.events import ThreadRef

await bot.send_message("spaces/AAA", text="top-level")
await bot.send_message(
    "spaces/AAA",
    text="threaded",
    thread=ThreadRef(name="spaces/AAA/threads/T1"),
    reply_option=MessageReplyOption.REPLY_OR_FAIL,
)
```

Use the imperative form in background jobs, Workspace Event handlers, or when
the destination is not the current interaction Space.

## Private message

The canonical private happy path is `Bot.send_message(..., private_to=...)`:

```python
await bot.send_message(
    "spaces/AAA",
    text="Only Alice and the app can see this",
    private_to="users/alice",
)
```

Private messages require app authentication. Chattice fails closed when the
viewer is empty or malformed and rejects incompatible accessory widgets before
network I/O. There is no `private_reply` helper.

## Cards, notifications, IDs, and CRUD

`Bot.send_message` also accepts `card=`, `accessory_widgets=`, `notify=`
(`"force"` or `"silent"`), `request_id=`, and `message_id=`. Notification
options and accessory widgets require app auth. Private accessory widgets stay
unsupported because Google's published constraints conflict; use a private
plain-text/card message without accessory widgets.

```python
message = await bot.get_message("spaces/AAA/messages/M1")
await bot.update_message(message.name, text="updated")
await bot.delete_message(message.name)
```

Use request/message IDs for idempotent application workflows; HTTP delivery
can be retried. Read metadata such as `attachments`, `annotations`, `mentions`,
`quote`, reaction summaries, `is_private`, and `is_silent` from
`MessageEvent`. Fields without a curated facade remain available through
`message.raw`.

Google mapping: `spaces.messages.create`, `get`, `update`, and `delete`.

Next: [Native commands](commands.md).

## Privacy model

Four distinct Google surfaces, chosen explicitly by the application:

| Surface | How | Visible to |
| --- | --- | --- |
| Shared Space message | `bot.send_message(space)` | everyone in the Space |
| Thread reply | `bot.send_message(space, thread=...)` or `message.reply()` | the thread participants |
| Private message | `bot.send_message(space, private_to=user)` | only `privateMessageViewer` (app auth required; no accessory widgets/attachments) |
| DM | send into the direct-message Space | only you and the app |

Dialogs are a separate synchronous surface: visible only to the opener,
HTTP-only. App Home is the persistent personal surface (HTTP-only).
Nothing is implicitly private and nothing implicitly becomes a Thread —
the application chooses the surface per runtime capabilities.

Local files attach to messages via `attachments=[InputFile(...)]` —
upload requires USER authentication and private messages cannot carry
attachments. See [Files, Images & Media](files-media.md).

