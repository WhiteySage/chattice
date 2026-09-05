# Changelog

All notable changes are documented here. Versions follow Python packaging
conventions. Before 1.0, incompatible changes may be released in a minor
version and will include upgrade notes.

## [0.3.4] — Examples and documentation corrections

### Fixed

- Pub/Sub examples configure subscriber credentials separately and close bot clients reliably.
- Message filters and conversation examples handle mentions and invalid input consistently.
- Documentation reflects current transport, membership, media, and dialog APIs.
- Release metadata and the dependency inventory match the package version.

### Added

- Executable documentation examples and scenario tests for the example applications.

## [0.3.3] — Test hardening and aiogram-mirroring examples

### Added

- Pub/Sub pull runner tests for the `run()`/`close()` lifecycle, ACTIVE
  claims, renewal terminal paths, and the parse and answer-routing
  branches; runner coverage rises from 74% to 99%.
- Coverage of `chattice.testing` closed to 100% (MockBot attachments,
  identity facades, assertion failures, EventFactory coercions).
- Flat examples mirroring the aiogram example set: `echo_bot`,
  `echo_bot_webhook`, `error_handling`, `finite_state_machine`,
  `own_filter`, `specify_updates`, `context_addition_from_filter`,
  `without_dispatcher`.

### Changed

- The public API test tracks the pyproject version instead of a pinned
  literal.
- Examples use a flat module layout. The Google-native capability tour
  lives in `examples/docs/from_zero.py` and the guides.

### Fixed

- Stale documentation references to the removed example paths.

## [0.3.2] — setUpSpace human-member fix

### Fixed

- `bot.user.spaces.get_or_setup_direct_message` now marks the setup
  membership as `User.Type.HUMAN`; gRPC rejected the request with
  `TYPE_UNSPECIFIED` before.

## [0.3.1] — Documentation and release-gate alignment

### Changed

- Guides, architecture pages, examples, and the release smoke test use
  the curated facade (`bot.app.*` / `bot.user.*`) everywhere; no sample
  teaches a pre-0.3 call form.
- `scripts/gen_sbom.py` fails fast when the chattice entry is missing
  from `uv.lock`; the committed SBOM is regenerated for this release.

### Fixed

- Stale documentation statements corrected: raw-access guidance,
  attachment-download identity semantics, operation names in the Pub/Sub
  page, retry-table operation keys, and outdated version references.

## [0.3.0] — Legacy outbound surface removed (ADR-013)

### Removed

- The pre-0.2 `Bot` convenience methods: `send_message`, `update_message`,
  `get_message`, `delete_message`, `get_space`, `list_spaces`, `add_member`,
  `get_member`, `list_members`, `remove_member`, `upload_attachment`,
  `download_attachment`, `get_attachment`. Every operation lives on the
  identity-bound resource clients (`bot.app.*` / `bot.user.*`) and runs
  through the single registry → executor path.
- `Bot.raw_client`; use `await bot.raw.app()` / `await bot.raw.user()`.
- `Bot.capabilities` and the `OutboundCapabilities`/`OutboundCapability`
  matrix; `chattice.capabilities.Operation` and the `OperationRegistry`
  are the single preflight.

### Changed

- `MessageEvent.reply()`, `ThreadRef.send()`, and `SpaceRef.send()` are
  unchanged as DX and now delegate to `bot.app.messages.create(...)`
  (previously the removed wrapper). Reply-option defaults are unchanged.
- A zero-credential call fails closed with `CapabilityNotSupported`
  before any client construction or transport work, for both identities.
- `Memberships.create(parent, *, user=, group=)` canonicalizes the
  parent (`"AAA"` → `spaces/AAA`) and the user target
  (`"user-123"` → `users/user-123`); `memberships.get/delete` validate
  the canonical `spaces/{space}/members/{member}` name locally.
- `MockBot` exposes the same `bot.app` / `bot.user` resource facade as
  the real Bot; recorded call kinds are unchanged (`send_message`,
  `update_message`, ...).

### Upgrade notes

- `bot.send_message(space, text=...)` → `bot.app.messages.create(space,
  text=...)` (or `bot.user.messages.create(...)` for user-identity
  sends; attachment sends must use the USER namespace).
- Media: `bot.user.attachments.upload()`,
  `bot.app.attachments.download()` / `bot.user.attachments.download()`,
  `bot.app.attachments.get_metadata()`.
- The full removal → replacement map is in
  [stability](docs/stability.md).

## [0.2.1] — Media through the executor

### Changed

- `upload_attachment` and `download_attachment` run through the
  `OperationExecutor`; the legacy APP-with-USER-fallback selection of
  `download_attachment` stays in the method wrapper.

## [0.2.0] — Curated outbound facade

### Added

- Operation registry as the single source of outbound auth truth
  (`Operation`, `OperationSpec`, `AuthPath`, `ExecutionVariant`,
  `OperationRegistry`) with local preflight semantics; the legacy
  `OutboundCapability` enum is frozen and maps one-way onto operations.
- Identity-bound resource clients: `bot.app.*` / `bot.user.*` for
  `spaces`, `messages`, `memberships`, `reactions` (USER-only), and
  per-user state (`read_state`, `thread_read_state`,
  `notification_setting`). Identity is always explicit; no automatic
  APP/USER fallback.
- `OperationExecutor` — one execution path for every registered
  operation: spec lookup, preview gating, registry preflight, identity
  client resolution, and the curated error policy.
- `RequestConfig` per-call GAPIC configuration (`timeout`, `retry`,
  `metadata`) with raw-GAPIC-compatible defaults; `Pager` for explicit
  async pagination.
- `bot.raw.app()` / `bot.raw.user()` async raw access split by identity.
- `bot.user.spaces.find_direct_message` and USER-only
  `get_or_setup_direct_message` with explicit `timeout=` and the
  official `Space.space_uri` for opening a direct chat.
- `bot.warmup()` to resolve credentials and build clients before the
  first event; `Bot(enable_preview=True)` opt-in for preview operations.
- Runtime hardening: synchronous handlers rejected at registration,
  structured lifecycle diagnostics (`handler_started` before
  invocation), stage-tagged error logs, Pub/Sub delivery identity and
  age, per-message card update serialization, `RuntimeDiagnostics`
  thresholds, `Dispatcher(strict_interactions=True)`, router path
  identifiers, and observability hooks for handlers, outbound calls,
  and delivery ACK/NACK.
- Typed `RequestConfigResponse` for the `REQUEST_CONFIG` interaction
  response.
- CI verifier comparing the operation registry with the Google Chat
  discovery document.

### Changed

- Legacy `get_message`, `delete_message`, `get_space`, `list_spaces`,
  `add_member`, `get_member`, `list_members`, and `remove_member`
  delegate to resource clients and share the single executor path.
- Unhandled failures log exception classes and stages; exception text
  and tracebacks are DEBUG-only.

## [0.1.3] — Diagnostics and typed API errors

### Added

- DEBUG routing diagnostics for event receipt, observer selection, handler
  matching, and handler result types.
- Structured Pub/Sub answer and failure logs with delivery context,
  exception messages, and tracebacks without raw event payloads.
- `ChatAlreadyExistsError` for already-existing resources and HTTP 409
  Chat API failures.
- Public documentation for handler dependency injection, action data,
  typed Chat API errors, and production troubleshooting.

### Fixed

- Dependency-resolution errors now identify the handler, unresolved
  parameter, and event type.
- Membership and Space-list operations consistently expose the existing
  typed `ChatAPIError` hierarchy.

## [0.1.2] — Initial public release

### Added

- Async dispatcher, routers, middleware, dependency injection, filters, and
  typed Google Chat interaction events.
- HTTP, Pub/Sub, streaming-pull, and Google Workspace Events integrations.
- Async Google Chat API client with app and delegated-user authentication.
- Typed Cards v2 builders, dialogs, forms, App Home responses, card updates,
  attachments, and optional Card image publishing.
- Finite-state storage, idempotency storage, Redis integrations, lifecycle
  resources, and observability hooks.
- FastAPI integration, testing helpers, runnable examples, API reference, and
  deployment guidance.
- Raw Google payload and client escape hatches for forward compatibility.
- Automated dependency, Google Chat schema, Cards SDK, and release-note
  monitoring.

### Compatibility

- Python 3.11, 3.12, and 3.13.
- Google Chat API v1 and Cards v2.
- The package distribution and Python import are both named `chattice`.
