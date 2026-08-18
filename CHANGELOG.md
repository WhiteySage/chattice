# Changelog

All notable changes will be documented here. The project follows Semantic
Versioning after the first public release; pre-1.0 APIs may change.

## [0.14.0b4] — 2026-08-17 — silent-miss diagnosis, redis hints, docs polish, upstream watch

- FormFilter/ActionDataFilter log decode failures at DEBUG (silent-miss
  diagnosis without changing filter semantics)
- Redis storages raise a friendly 'install chattice[redis]' hint
- deployment recipes, Pub/Sub console setup, cookbook recipes,
  pytest example, aiogram side-by-side skeletons, README two-startup
  block, brand assets
- dependabot google groups, weekly upstream watcher, pip-audit in CI
- removed committed iCloud duplicate files

## [0.14.0b3] — 2026-08-16 — pip-canonical docs, public examples cleaned, clean public history

(b1/b2 were published; b3 ships the final pre-launch polish.)

## [0.14.0b2] — 2026-08-16 — README absolute docs links for PyPI

(0.14.0b1 was published; b2 ships the README URL fix and project URLs.)

## [0.14.0b1] — 2026-08-16 — first public beta release

(0.14.0 was the pre-release candidate; the public beta ships as
0.14.0b1 per ADR-011.)

## [0.14.0] — public beta release

### Added

- Core-boundary remediation: independent Workspace Events runtime, typed
  command kinds and action sources, explicit preview enrollment, transport-
  uniform response-capability DI, and lossless unknown Cards JSON fallback.
- The optional AI integration moved from `chattice.ai` to
  `chattice.experimental.ai`; it remains in the distribution but is explicitly
  outside the stable core API.
- Additive DX enrichment: zero-fetch contextual sends, direct ActionData
  button binding, and immutable read-side message metadata accessors. The
  imperative `Bot.send_message()` API remains fully supported and unchanged.
- Scope-aware outbound local preflight: known user/app credential scopes now
  filter message capabilities through documented any-of rules without hidden
  network calls; unknown scopes preserve backward-compatible behavior.
- Project rename to **Chattice** (ADR-010) and the versioning policy
  (ADR-011): this is the FIRST PUBLIC BETA CANDIDATE.
- Owner-safe push idempotency state machine (claim/complete/release,
  429 on active, atomic expired-lease takeover, bounded completed
  retention).
- Race-safe FSM lazy expiry (compare-and-delete) and the full FSM
  record/CAS storage model.
- Class-only framework error logging — handler exception messages
  (potentially secret-bearing) never reach logs; runtime redaction
  regression test.
- Human documentation product (troubleshooting, enterprise and
  deployment guides, mkdocstrings API reference, aiogram side-by-side,
  mental models), coding-agent documentation (docs/agents, PUBLIC_API),
  OSS repository hardening (CONTRIBUTING/SECURITY/CoC/templates/
  policies), license & provenance audit, curated sdist policy.

### Status

**Pre-1.0 beta / release candidate.** The documented stable beta surface is
frozen against incompatible change; additions remain possible. Experimental
and raw/advanced surfaces carry their separate contracts. Not published to
PyPI.

## [0.13.0] — development release

### Added

- Phase 14 gap closure: Workspace Events official Pub/Sub binding,
  slash commands / link previews / sender-aware card responses,
  dedupe claim/complete/release, secure-by-default push verification,
  capability-model split, off-loop verification and Bot.close(),
  ActionData, AccessoryWidget, FSM records, FormModel, lifespan,
  RawWidget, response validation.
- Phase 15 dogfooding scenarios + CRM workflow; post-review
  reconciliation (8 blockers); selective gap audit (argument_text,
  notification options, private viewer, card updates, poll recipe).

## [0.12.0]

### Added

- Value-first README and Getting Started; honest aiogram comparison;
  public API audit.
- Named example bots (echo/command/buttons/form/dialog/fsm/fastapi/pubsub/
  workspace_events), each executable and test-covered.
- Reproducible fresh-venv package verification script.

### Status

**Pre-1.0 beta / release candidate.** The public API may still change
before 1.0.0 (semver applies to post-1.0 releases only). Not published
to PyPI.

## [0.11.0]

### Added

- `chattice.testing`: MockBot (call recorder with message assertions),
  EventFactory (typed event builders — no raw Google JSON in unit tests),
  FakeChatTransport (migrated; compat re-export), card assertions,
  FSM seeding helper.
- Live integration suite skeleton (`tests/integration/live`) with an
  honest skip and full setup instructions.

## [0.10.0]

### Added

- `chattice.idempotency`: IdempotencyStorage protocol, Memory +
  Redis implementations (SET NX EX — single-command atomicity);
  Pub/Sub push-router dedupe by messageId.
- `chattice.observability`: ObservabilityHooks + Dispatcher
  observability_hooks (additive, failure-isolated).
- Bot: per-call `timeout` on all operations.
- Architecture docs: reliability (retry classification, verified quotas,
  backoff guidance), observability (OTel bridge example), security audit
  with a source-scan redaction test.

## [0.9.0]

### Added

- Pub/Sub push ingress: PubSubPushAdapter (documented envelope ->
  interaction event), create_pubsub_router (204 ack, no sync responses);
  capability rows for transport="pubsub".
- Workspace Events ingress family: WorkspaceEvent model, CloudEvent
  parser, workspace_event observer, create_workspace_events_router.
- SubscriptionManager protocol skeleton (implementation deferred).

## [0.8.0]

### Added

- `chattice.auth`: CredentialsProvider (canonical home), lazy
  ServiceAccountCredentialsProvider (file/info), UserCredentialsProvider
  with lazy refresh; AuthMode; CHAT_BOT_SCOPE. Client re-exports the
  protocol for Phase 4 compatibility.
- `chattice.capabilities`: Capability matrix (single source of truth,
  verified Google facts), Capabilities.require() guards that fail BEFORE
  network calls; capabilities injected into handler context.
- `chattice.experimental`: preview-feature namespace marker.

## [0.7.0]

### Added

- `chattice.fsm`: State/StatesGroup, FSMContext (name-based DI via
  `data["state"]`), StorageKey + FSMStrategy on Google refs (default
  USER_IN_SPACE), MemoryStorage, StateFilter, FSMError.
- Dispatcher(fsm_storage=..., fsm_strategy=...) pre-injects the FSM
  context before filter evaluation (additive; unconfigured behavior
  unchanged).
- `chattice[redis]` extra: RedisStorage (per-command atomicity only —
  update_data is not cross-process, documented honestly).

## [0.6.0]

### Added

- Dialogs: Button/Action `interaction=OPEN_DIALOG`, `Dialog` facade,
  `ActionStatus.ok/.invalid`; DIALOG/actionStatus sync responses;
  `router.dialog_submit` / `router.dialog_cancel` observers.
- Forms: full TextInput/SelectionInput/DateTimePicker fields, `Validation`
  facade (character limit + input type); Section.from_proto rebuilds form
  widgets (Phase 5 debt closed).
- App Home: RenderActions pushCard (APP_HOME) and updateCard (SUBMIT_FORM)
  sync responses.

## [0.5.0]

### Added

- `chattice.cards`: typed facade builders over the official
  google-apps-card SDK — Card, CardHeader, Section, TextParagraph,
  Divider, ButtonList, Button (action/parameters or open link), Action,
  OpenLink, TextInput, SelectionInput, DateTimePicker; serialization to
  documented Cards v2 JSON; raw proto escape hatch.
- FastAPI integration: handlers may return a Card — MESSAGE replies with
  `cardsV2`; CARD_CLICKED replies with `actionResponse UPDATE_MESSAGE`
  (documented bot-message card replacement).

## [0.4.0]

### Added

- `chattice.client`: `Bot` — async outgoing Chat API operations
  (`send_message`, `get_message`, `update_message`, `delete_message`,
  `get_space`) over the official `google-apps-chat` SDK with a lazy
  grpc_asyncio client; `raw_client` escape hatch; `MessageReplyOption`
  thread semantics; `request_id` idempotency passthrough.
- `ChatAPIError` hierarchy wrapping SDK errors with preserved code/details
  and chaining; `CredentialsProvider` protocol.

## [0.3.0]

### Added

- `chattice.transports.http`: web-framework-neutral HTTP interaction core —
  `IncomingRequest`, `InteractionResponse` with double-response guard,
  `InteractionContext` with the documented 30-second sync deadline,
  `HTTPInteractionAdapter`, `GoogleTokenVerifier` (google-auth based,
  both documented audience strategies), `MockVerifier`.
- `chattice.integrations.fastapi`: `create_chat_router()` for FastAPI
  (optional extra `chattice[fastapi]`), also usable under plain Starlette.
- Verification failures map to HTTP 401 per the official docs; malformed
  payloads to 400; handler failures to 500.

## [0.14.0b5] — media attachments, regex filters, dual-identity auth

- Added `chattice.media`: `InputFile` (from_path/from_bytes, lazy reads,
  local preflight), `UploadedAttachment` (space-scoped), typed
  `AttachmentRef`/`AttachmentSource` and the additive
  `MessageEvent.attachment_refs` accessor.
- Added the Bot media flow: `upload_attachment` (USER auth),
  `download_attachment` (USER or APP), `get_attachment` (APP + chat.bot),
  `send_message(attachments=...)` and `attachments=` on contextual sends —
  the whole set is preflighted locally, then uploaded sequentially.
- Added dual-identity Bots: `app_credentials_provider` /
  `user_credentials_provider` with capability-based identity selection and
  `DelegatedUserCredentialsProvider` (Domain-Wide Delegation via
  `with_subject` — one service-account JSON for both identities).
- Added outbound capabilities `ATTACHMENT_UPLOAD`, `MEDIA_DOWNLOAD`,
  `ATTACHMENT_METADATA_GET` with the documented scope matrix.
- Added the typed Cards v2 `Image` widget (HTTPS-only, `on_click` via the
  existing Action/OpenLink facades).
- Added `F.text.regexp(pattern, flags=)` — Python-regex routing with
  `re.match` semantics, compiled once at filter construction.
- Added the optional `chattice[media]` extra (official REST media
  endpoints; the GAPIC client cannot carry a binary media body).
- Added the `Files, Images & Media` guide.

## [0.14.0b6] — attachment identity correctness, media preflight hardening

- Fixed attachment message identity routing: `send_message(attachments=...)`
  now performs the WHOLE send — `media.upload` AND the final
  `messages.create` — with the USER identity (live-verified: an
  APP-authenticated create cannot consume a USER-uploaded attachment;
  the sender of an attachment message is the authenticated/impersonated
  USER). The Bot gained a cached single-flight USER Chat client that
  closes together with the APP client; effective-identity capability
  preflight rejects `notify`/`card` combinations with attachments
  locally.
- Fixed the `InputFile` read path TOCTOU window: files are opened once
  with `O_NONBLOCK` and re-checked from the descriptor (regular symlinks
  are honored; a path swapped to a FIFO fails closed instead of hanging).
- Added batch Workspace Event type constants
  (`message/reaction/membership.v1.batch*`, `space/spaceReadState/
  threadReadState.v1.batchUpdated`) alongside the forward-compatible
  parser.
- Documented the USER end-to-end attachment send semantics (sender =
  HUMAN), corrected the DWD guidance, and added an ordinary-OAuth
  development recipe.

## Unreleased

- Added the pure Google Chat interaction adapter for all eight stable event
  types, direct/App Home envelopes, typed common/form data, and explicit parser
  exceptions.
- Added immutable actor/space/thread/message references, lifecycle, command,
  widget, App Home, form-submit, and dialog metadata domain values.
- Added dedicated routing observers and provenance-recorded Google fixtures.
- Added immutable synthetic domain events.
- Added the Phase 1 dispatcher, nested routers, observers, filters, middleware,
  dependency injection, routing control, and error routing.
- Added comprehensive core-engine tests, executable examples, and architecture
  documentation.

## 0.0.0

- Added Phase 0 research, architecture, ADRs, and repository scaffold.
