# Troubleshooting

Format: Symptom → Cause → Verify → Fix.

## Bot receives no events

- **Cause:** the HTTP endpoint is not verified / wrong audience; the Chat
  app is not in Live mode; the handler router is not included.
- **Verify:** `curl` the endpoint with a malformed body — a configured
  app answers 401 (verifier) or 400 (parse), never silence. Check the
  `chattice.http` logs.
- **Fix:** `create_chat_router(dispatcher, GoogleTokenVerifier(audience="<endpoint URL>"))`;
  include the router (`dispatcher.include_router(router)`).

## Command not triggered

- **Cause:** slash commands arrive as `MESSAGE` events with
  `message.slashCommand`; quick commands as `APP_COMMAND`. Routing both
  through a string `F.text.startswith("/")` filter is wrong.
- **Verify:** log `event` type — a native slash command must be a
  `CommandEvent(kind=CommandKind.SLASH_COMMAND)`.
- **Fix:** register `@router.command()` (one handler serves both
  families) — see the native command section of
  `examples/docs/from_zero.py`.

## Command ID mismatch

- **Cause:** the numeric `command_id` in the payload differs from the
  Chat app configuration.
- **Verify:** `command.command_id` in the handler; compare with the
  Google Chat app config.
- **Fix:** re-check the app configuration; when needed, route by id in
  the handler body.

## 401 / 403

- **Cause (401):** incoming verification failed (wrong audience/issuer);
  push verification failed (missing/wrong service-account identity).
- **Cause (403):** authenticated API call lacks scopes or the app is not
  a member of the Space.
- **Verify:** the `chattice.http`/`chattice.push` logs name the
  failing verifier stage.
- **Fix:** check the audience string; for push pass
  `GooglePubSubVerifier(audience=..., service_account_email=...)`; grant
  `chat.bot`; add the app to the Space.

## Action button does nothing

- **Cause:** the action response needs the message sender type and the
  payload lacks `message.sender` (serializer refuses to guess); or the
  handler returns `ActionStatus` for a plain click (dialog-only
  response).
- **Verify:** the HTTP response is 500 with the serialization log line.
- **Fix:** ensure the payload carries `message.sender.type`; answer
  plain clicks with text/updated Card — `ActionStatus` only on
  `SUBMIT_DIALOG`.

## Dialog fails

- **Cause:** `DateTimePicker` inside a `Dialog` (documented Google
  constraint); or a `Dialog` returned for a non-dialog, non-command
  event.
- **Verify:** the construction-time `ValueError` or the serializer
  error names the exact violation.
- **Fix:** move pickers to card messages; open dialogs from commands or
  `OPEN_DIALOG` interactions only.

## Pub/Sub capability mismatch

- **Cause:** Pub/Sub push has NO synchronous response channel: handlers
  answering with cards/dialogs are ignored, and dialogs are not
  delivered.
- **Verify:** `ResponseCapabilities.resolve(transport="pubsub", ...)`
  is empty for sync/dialog capabilities.
- **Fix:** answer push with nothing (204); update cards via
  `bot.app.messages.update(name, card=...)` afterward.

## Request timeout

- **Cause:** long work in a synchronous interaction handler (30 s
  deadline).
- **Verify:** the latency warning in the HTTP logs.
- **Fix:** answer the interaction immediately; continue with
  `Bot` calls (the response-lifecycle boundary — see
  [Forms vs FSM vs Scenes](architecture/forms-vs-fsm-vs-scenes.md#response-lifecycle-sync-vs-deferred)).

## Redis state disappears

- **Cause:** `MemoryStorage` used as if durable; or the whole-record
  `expires_at` TTL elapsed.
- **Verify:** which storage class is wired into the Dispatcher.
- **Fix:** use `RedisStorage`/`RedisFSMRecordStorage` for durable state;
  check `expires_at` on the record.

## Duplicate interaction

- **Cause:** Pub/Sub redelivery after a 500/429; handlers must be
  idempotent.
- **Verify:** the push logs show claim/complete/release transitions.
- **Fix:** keep handlers idempotent; the owner-safe idempotency state
  machine absorbs completed duplicates and returns 429 for active ones.

## Attachment upload failure

- **Cause:** attachment sends are USER-authenticated end to end —
  `media.upload` AND the final `messages.create` run on the USER client.
  An app/service-account-only Bot cannot send attachments; the Bot fails
  locally with `CapabilityNotSupported` naming the missing user identity.
- **Verify:** the exception type — a local `CapabilityNotSupported`
  (no network) vs `ChatPermissionDeniedError` (Google denied it).
- **Fix:** configure a dual-identity Bot:
  `Bot(app_credentials_provider=..., user_credentials_provider=...)`.
  Inside Google Workspace, `DelegatedUserCredentialsProvider` reuses the
  same service-account JSON with a `subject=` (Domain-Wide Delegation);
  with end-user OAuth use `UserCredentialsProvider`. A user-authenticated
  call acts on behalf of that user — the attachment message is sent from
  the USER identity (`sender.type = HUMAN`). See
  [Files, Images & Media](guides/files-media.md).

## Media extra missing

- **Cause:** media operations require the optional REST client (the
  GAPIC SDK cannot carry a binary media body).
- **Verify:** the error carries an install command.
- **Fix:** `pip install "chattice[media]"`.

## Drive-backed attachment download

- **Cause:** `media.download` serves Chat-uploaded content only; a
  `DRIVE_FILE` reference needs the Drive API.
- **Verify:** `attachment_refs` reports `is_drive` and a `drive_file_id`.
- **Fix:** call the Google Drive API with that id; Chattice rejects the
  Chat media path locally with an actionable message.

## Space identifier error

- **Cause:** a display name ("Finance") passed where a Space id/name is
  expected — Chattice never performs hidden display-name lookups.
- **Verify:** the error names the malformed Space reference.
- **Fix:** pass `"AAA"` or `"spaces/AAA"` or a `SpaceRef`; resolve
  display names explicitly in application code.

## A button "does nothing"

Card actions route through `@router.action("name")`; typed forms and
ActionData go through filters. If the incoming parameters or form values
cannot decode into the declared model, the FILTER does not match and the
handler is silently skipped (a filter mismatch is not an error). Enable
the debug loggers to see the decode reason:

```python
import logging

logging.getLogger("chattice.forms").setLevel(logging.DEBUG)
logging.getLogger("chattice.actions").setLevel(logging.DEBUG)
```

Check that the widget names in the card match the model field names
exactly, and that the Google interaction actually carries
`common.formInputs` / action parameters.

## ImportError: No module named 'redis'

Redis-backed storages require the optional extra:

```bash
pip install "chattice[redis]"
```


## Upgrading from 0.1.x (migration notes)

Behavior changes in 0.2 are additive diagnostics plus one early-fail rule:

- **Sync handlers now fail at registration.** `def handler(...)` raises
  `InvalidHandlerError` the moment `@router.action(...)` runs — the body
  never executes. In 0.1 the same mistake failed only after the first
  event. Fix: declare handlers `async def`.
- **Unmatched actions/commands log at WARNING** (`unhandled interaction` /
  `unhandled command`) instead of the old DEBUG-only `no handler matched`
  (which remains for non-interactive events). Opt into
  `Dispatcher(strict_interactions=True)` to turn these into
  `UnhandledInteractionError`.
- **Failure logs are safer:** unhandled exceptions log the exception CLASS
  (`exception_type=...`) and stage, never the message text. Tracebacks
  appear only when the logger runs at DEBUG.
- **New configurable thresholds:**
  `RuntimeDiagnostics(slow_handler_ms=1000, delayed_event_ms=5000)` — pass
  to `Dispatcher(runtime_diagnostics=...)`; `None` disables a warning.
- **APP/USER raw access:** `bot.raw.app()` / `bot.raw.user()` are the
  explicit-identity replacements for `bot.raw_client` (removed in 0.3.0).
- **New curated wrappers:** `bot.user.spaces.find_direct_message(...)` and
  `bot.user.spaces.get_or_setup_direct_message(...)` (USER-only), both with
  a `timeout=` argument.

The `Bot` convenience methods (`send_message` and the rest) and
`bot.raw_client` were removed in 0.3.0 — see
[stability](stability.md) for the migration map. Everything else in the
0.1.x public API — enums, Router decorators, HTTP transport, Pub/Sub
push/pull, Workspace Events, Card/string/None result handling — is
unchanged.
