# Debugging Chattice applications

Chattice keeps detailed route diagnostics at DEBUG level and avoids logging
raw Google Chat event bodies by default. Start with the loggers that cover
the inbound path, routing, and deferred Pub/Sub work:

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("chattice.routing").setLevel(logging.DEBUG)
logging.getLogger("chattice.pubsub").setLevel(logging.DEBUG)
logging.getLogger("chattice.runtime").setLevel(logging.DEBUG)
```

## My button works only on the second click

`spinner → nothing → click again → works` is almost always Pub/Sub delivery
lag, not a routing bug. Each delivery logs its identity and age
(`chattice.pubsub`, INFO):

```text
delivery received: pubsub_message_id=... delivery_attempt=0 event_type=action
action=start_main message_resource_name=spaces/A/messages/M1
space_resource_name=spaces/A received_time=... event_time=... event_age_ms=48321
delivery_kind=new
```

- `delivery_kind=redelivery` and a high `event_age_ms` mean a backlog: the
  first click was simply delivered late. Check the subscription backlog and
  add the WARNING threshold via `RuntimeDiagnostics(delayed_event_ms=...)`.
- `WARNING delayed interaction received` fires when `event_age_ms` exceeds
  the threshold (default 5000 ms).
- `WARNING stale interaction detected` means an OLDER click for the same
  card arrived after a newer one was already processed. The stale event is
  still executed (handlers may hold business side effects) but the warning
  names the card and the two timestamps.
- A slow Google API answer can look the same: the `acked` log splits
  `handler_duration_ms`, `outbound_operation`, `outbound_duration_ms`, and
  `total_duration_ms` — see which side of the boundary is slow.
- Concurrent actions updating ONE card are serialized inside the process
  (different cards stay parallel); multi-instance global ordering is not
  guaranteed.

## Handlers must be async

A synchronous handler is rejected at REGISTRATION time — its body never
runs, and no side effect can escape:

```python
# wrong — raises InvalidHandlerError at registration:
@router.action("foo")
def foo(): ...


# correct:
@router.action("foo")
async def foo(): ...
```

`InvalidHandlerError: Handler '...' must be asynchronous. Declare it using
'async def'.` also rejects sync callable objects. Decorated async functions
(`functools.wraps`) and objects with an `async def __call__` are accepted.

## Using synchronous SDKs

The framework never wraps sync handlers in `asyncio.to_thread` for you —
the thread boundary is your responsibility:

```python
async def handler(message: MessageEvent) -> None:
    result = await asyncio.to_thread(sync_sdk_call, message.text)
```

The same pattern applies to `gspread`, sync HTTP SDKs, filesystem/credential
providers, and legacy sync libraries. Blocking the loop makes handlers hang;
watch `WARNING slow handler` under `chattice.runtime` (threshold via
`RuntimeDiagnostics(slow_handler_ms=...)`).

## Understanding lifecycle logs

Every delivery walks explicit stages. `handler_started` is logged BEFORE the
callback runs, so a hung handler never looks like silence:

```text
DEBUG chattice.routing   event received: ...
DEBUG chattice.routing   routing started: ...
DEBUG chattice.routing   observer selected: router=... observer=action
DEBUG chattice.routing   handler_selected: ... handler=app.handlers.foo
INFO  chattice.routing   handler_started: handler=app.handlers.foo
INFO  chattice.routing   handler_completed: handler=app.handlers.foo result_type=Card
DEBUG chattice.pubsub    answer_started: ... mode=update_message
INFO  chattice.pubsub    card updated: message=...
DEBUG chattice.pubsub    answer_completed: ... mode=update_message
INFO  chattice.pubsub    acked: message_id=... event_type=action
```

If the log stops after `handler_started`, the handler is still running (or
hung). If it stops between `answer_started` and `answer_completed`, the
Google API call is in flight.

## Unmatched interactions are loud

An action or command without a handler is a WARNING, not silence:

```text
WARNING chattice.routing unhandled interaction: event_type=action action=start_main
WARNING chattice.routing unhandled command: event_type=command command_id=7
```

In DEBUG mode the log also lists registered action names. To treat an
unmatched interactive event as a configuration error, enable
`Dispatcher(strict_interactions=True)` — it raises
`UnhandledInteractionError`. Unmatched non-interactive events stay DEBUG-only.

## The handler raises an exception

An unhandled failure always leaves one structured ERROR in
`chattice.runtime` — exception CLASS only, never the message (it may
contain form values, tokens, or user text):

```text
ERROR chattice.runtime handler failed: event_type=action action=open_info
handler=app.handlers.open_info exception_type=PermissionDenied stage=handler
message_id=spaces/A/messages/M1
```

`stage` tells you where the failure escaped: `filter`,
`dependency_resolution`, `middleware`, `handler`, `outbound_send_message`,
`outbound_update_message`, plus the Pub/Sub stages (`claim`, `ack`, `nack`).
At DEBUG level the same records carry the full traceback, including exception
messages. Those messages may contain application data; enable DEBUG only where
that output is appropriate. The framework does not separately serialize raw
event payloads into logs.

## A Card result does not update the clicked message

For pull Pub/Sub, a returned Card updates the clicked bot message only when
the parsed `ActionEvent` includes `event.message.name`. Otherwise Chattice
sends the Card as a new message. The runner logs:

```text
DEBUG chattice.pubsub answer_started: event_type=action result_type=Card mode=update_message
INFO  chattice.pubsub card updated: message=spaces/.../messages/...
```

An update failure logs `outbound failed: ... stage=outbound_update_message`
(exception class only) and follows the normal retry/poison-message policy.

## APP vs USER authentication

APP and USER identities have different semantics:

- **APP** — the bot acts as itself. Default for outgoing messages, card
  updates, space management.
- **USER** — the bot acts on behalf of a Workspace user. Required for
  attachment uploads and for operations that need a user's private spaces,
  such as finding/setting up a direct message.

Configure both on one bot:

```python
bot = Bot(
    app_credentials_provider=...,
    user_credentials_provider=...,
)
```

Identity is always explicit — the framework never picks one for you based
on scopes. Use the identity namespaces:

```python
space = await bot.user.spaces.find_direct_message("hr@example.com")
space = await bot.app.spaces.find_direct_message("users/123456789")
```

## Raw access

```python
app_client = await bot.raw.app()  # raw APP-authenticated SDK client
user_client = await bot.raw.user()  # raw USER-authenticated SDK client
```

The legacy `bot.raw_client` was removed in 0.3.0 — the explicit
`bot.raw.app()` / `bot.raw.user()` forms are the only raw access (see
[stability](../stability.md) for the removal map).

## Event never reaches the app

For HTTP, check the verifier audience and endpoint path. A rejected request
is logged by `chattice.http` and returns 401; an invalid body returns 400.
For Pub/Sub push, configure `PubSubPushVerifier` and inspect
`chattice.push`. For pull, confirm the subscription and credentials used by
`Dispatcher.run_pubsub()`.

## Pub/Sub receives an event but the handler does not run

The pull runner logs the message id and attempt when processing begins. If
parsing fails, the delivery is nacked (or poison-acked at the configured
attempt limit) and the log identifies the parse failure without dumping the
payload. If routing completes without a match, `chattice.routing` emits
`no handler matched` for non-interactive events and a WARNING for
actions/commands (see "Unmatched interactions are loud" above).

## The wrong router or filter is selected

Check that every feature router is included in the Dispatcher:

```python
dispatcher.include_router(account_router)
```

At DEBUG level, `chattice.routing` reports the event type, selected observer,
router name, selected handler, and handler result type. For actions, compare
the logged `action=...` value with the function in `@router.action(...)`.
The string form `@router.action("start_user_manage")` is equivalent to
`@router.action(F.name == "start_user_manage")`.

## A missing dependency fails before the handler body

Event aliases (`event`, `message`, `action`, `command`, and the other
documented aliases) and typed Event annotations are injected automatically.
An arbitrary parameter is resolved only from dispatcher context, middleware,
or another DI provider:

```python
@router.slash_command(F.command_id == 1)
async def start(command: CommandEvent, bot: Bot) -> None: ...
```

`async def start(name): ...` does not receive the event as `name`. It raises
`DependencyResolutionError` naming the handler, parameter, and event type.
Pass `name=...` through the dispatch context or change the signature to a
typed event parameter. The failure log carries
`stage=dependency_resolution`.

## `form_inputs` versus `parameters`

Values entered into `TextInput`, `SelectionInput`, and other form widgets are
in `event.form_inputs`. Explicit values attached to a Button action are in
`event.parameters`. Matching keys do not merge the two mappings.

## NACK and redelivery

The pull runner releases its idempotency claim before nacking a failed
delivery, so a redelivery can retry it. The release and nack stages are
logged (`release_started`, `release_succeeded`, `delivery failed, nacked`
with the exception class). Once the configured maximum delivery attempt is
reached, Chattice sends a best-effort error notification when it has a
Space target and poison-acks the delivery. Successful deliveries are
completed before they are acked; later duplicates are absorbed
(`duplicate acked`, `delivery_kind=duplicate_completed`).

For push endpoints, `chattice.push` logs claim, release, and completion
failures. A failed dispatch returns a non-success response so Pub/Sub can
redeliver it.
