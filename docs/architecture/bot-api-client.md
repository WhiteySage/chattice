# Bot API client

Phase 4 adds the outgoing channel: `chattice.client.Bot` wraps the official
`google-apps-chat` SDK.

## Boundaries

- `client/` depends only on `events` (SpaceRef/ThreadRef). Dispatcher, Router,
  filters and middleware never import the client.
- Incoming verification credentials (Phase 3) and outgoing API credentials are
  separate concepts; nothing is shared between them.
- Handlers obtain the Bot through DI by name, `Dispatcher(bot=...)`, or a
  per-feed `bot=` context value.

## Bot

```python
bot = Bot(
    credentials=service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/chat.bot"],
    )
)
sent = await bot.send_message("spaces/AAA", text="hello")
await bot.update_message(sent.name, text="updated")
await bot.delete_message(sent.name)
```

The SDK client is created lazily on the first call (grpc_asyncio transport —
native async). `bot.raw_client` exposes the SDK client as an escape hatch.

## Two official send levels

`Bot.send_message()` remains the universal imperative API. It is the right
choice for jobs, workers, event consumers, services without interaction
context, or any call where the space name comes from application data.

When a handler already has Google Chat context, refs and messages offer direct
adapters over that same method:

```python
dispatcher = Dispatcher(bot=bot)


@router.message()
async def greet(message: MessageEvent) -> None:
    await message.reply("Hello")
    await message.thread.send("Same thread")
    await message.space.send("New top-level message")
```

These methods never call `get_space()` or fetch a message/thread. They issue
exactly one `Bot.send_message()` call using identifiers already present in the
event. `message.reply()` uses `REPLY_OR_FAIL`; a missing Bot, space, thread, or
thread parent fails locally before transport work.

Use object methods when you already have a Google Chat context. Use
`Bot.send_message()` when addressing a Space explicitly from services, jobs,
or application code outside an interaction handler.

## Thread semantics

`send_message(..., thread=ThreadRef(...))` sets `message.thread.name` and, by
default, uses `REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`; `reply_option=REPLY_OR_FAIL`
maps to `REPLY_MESSAGE_OR_FAIL`. Without a thread, the documented default
starts a new thread. `ThreadRef.thread_key` IS serialized to the wire: an app
can create its own thread with an app-defined `threadKey` (a live-verified
regression — the key was once dropped); replying into an EXISTING thread
requires the full `spaces/.../threads/...` resource name in `thread.name`.

## Idempotency

`request_id` maps to the documented `requestId`: retrying with the same ID
returns the originally created message. Google does not document a retention
window — do not rely on one.

## Errors

| SDK error | Framework error |
| --- | --- |
| NotFound | ChatNotFoundError |
| PermissionDenied / Forbidden | ChatPermissionDeniedError |
| InvalidArgument | ChatInvalidArgumentError |
| ResourceExhausted / TooManyRequests | ChatRateLimitError |
| ServiceUnavailable / 5xx | ChatServiceUnavailableError |
| Unauthenticated / Unauthorized | ChatUnauthenticatedError |
| anything else | ChatAPIError |

The original SDK exception is always preserved as `__cause__`; `.code` and
`.details` remain accessible. The framework does not retry blindly — apps
decide using the typed errors. The app must be a member of the space to act
(otherwise Google returns 403 «You are not permitted to use this app»).
