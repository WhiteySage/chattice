# Bot API client

The outgoing channel, `chattice.client.Bot`, wraps the official
`google-apps-chat` SDK.

## Boundaries

- The client uses event references, authentication providers, Cards, media,
  and the operation registry. It does not depend on a web server.
- Incoming verification credentials and outgoing API credentials are
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
sent = await bot.app.messages.create("spaces/AAA", text="hello")
await bot.app.messages.update(sent.name, text="updated")
await bot.app.messages.delete(sent.name)
```

The SDK client is created lazily on the first call (grpc_asyncio transport —
native async). Outbound operations follow the curated facade (ADR-012):

- `OperationRegistry` is the single source of outbound auth truth;
  every call preflights through it.
- Identity-bound resource clients (`bot.app.*` / `bot.user.*`) expose
  spaces, messages, memberships, reactions, and per-user state; identity
  is always explicit, never auto-selected.
- One `OperationExecutor` path runs every registered operation: spec
  lookup, preview gate, preflight, identity client, RPC, curated errors.
- The raw tier is split by identity: `await bot.raw.app()` /
  `await bot.raw.user()`.

Space and membership primitives use the same facade:

```python
pager = await bot.app.spaces.list(filter='spaceType = "SPACE"')
spaces = await pager.collect()
await bot.app.memberships.create("spaces/AAA", user="users/123")
membership = await bot.app.memberships.get("spaces/AAA/members/123")
pager = await bot.app.memberships.list(parent="spaces/AAA")
memberships = await pager.collect()
await bot.app.memberships.delete("spaces/AAA/members/123")
```

List operations return an explicit `Pager`; iterate it or `collect()` it.
Membership create/delete require the administrator-approved
`chat.app.memberships` scope; get/list accept that scope or `chat.bot`. The
registry auth paths for these operations never include USER credentials.

## Two official send levels

`bot.app.messages.create()` is the universal imperative API. It is the right
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

These methods never call `spaces.get()` or fetch a message/thread. They issue
exactly one `bot.app.messages.create()` call using identifiers already present
in the event. `message.reply()` uses the SDK's `REPLY_MESSAGE_OR_FAIL` option; a missing Bot, space, thread, or
thread parent fails locally before transport work.

Use object methods when you already have a Google Chat context. Use
`bot.app.messages.create()` when addressing a Space explicitly from services,
jobs, or application code outside an interaction handler.

## Media pipeline (explicit USER identity)

Local attachment upload requires USER authentication. A Bot can hold both
identity providers, but calls choose a namespace explicitly:

```python
from chattice.media import InputFile

await bot.app.messages.create("spaces/AAA", text="App message")
await bot.user.messages.create(
    "spaces/AAA", attachments=[InputFile.from_path("report.pdf")]
)
```

The attachment call validates the entire input set, uploads each local file,
and creates the message using the same USER identity. It does not fall back
to APP credentials. Contextual `message.reply()` uses the APP namespace.

Uploads and downloads use the optional `chattice[media]` extra
(google-api-python-client media endpoints) — the GAPIC client cannot
carry a binary media body. `bot.app.attachments.get_metadata()` uses the GAPIC
`get_attachment` (APP-only). Download accepts USER or APP; Drive-backed
references are rejected locally with a Drive-API hint. A
USER-authenticated call acts on behalf of that user.

Every outbound operation — GAPIC and REST alike — runs through the
OperationExecutor: spec lookup, preview gate, preflight, identity
client, and the curated error policy. Media upload and download use the
media REST endpoint inside their executor closure (the GAPIC client is
unused there); each is always called with an explicit identity taken
from its `attachments` namespace.

## Thread semantics

`messages.create(..., thread=ThreadRef(...))` sets `message.thread.name` and, by
default, uses `REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`. Pass
`CreateMessageRequest.MessageReplyOption.REPLY_MESSAGE_OR_FAIL` as
`reply_option` to require an existing thread. Without a thread, the documented default
starts a new thread. `ThreadRef.thread_key` IS serialized to the wire: an app
can create its own thread with an app-defined `threadKey`. Replying into an
existing thread requires the full `spaces/.../threads/...` resource name in
`thread.name`.

## Idempotency

`request_id` maps to the documented `requestId`: retrying with the same ID
returns the originally created message. Google does not document a retention
window — do not rely on one.

## Errors

| SDK error | Framework error |
| --- | --- |
| NotFound | ChatNotFoundError |
| AlreadyExists / Conflict (HTTP 409) | ChatAlreadyExistsError |
| PermissionDenied / Forbidden | ChatPermissionDeniedError |
| InvalidArgument | ChatInvalidArgumentError |
| ResourceExhausted / TooManyRequests | ChatRateLimitError |
| ServiceUnavailable / 5xx | ChatServiceUnavailableError |
| Unauthenticated / Unauthorized | ChatUnauthenticatedError |
| Other GoogleAPICallError | ChatAPIError |

Non-Google exceptions propagate unchanged. Wrapped SDK exceptions are
preserved as `__cause__`; `.code` and
`.details` remain accessible. The framework does not retry blindly — apps
decide using the typed errors. The app must be a member of the space to act
(otherwise Google returns 403 «You are not permitted to use this app»).
