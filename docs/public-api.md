# Public API Reference

Audit snapshot for the 0.14.0 beta candidate (2026-08-16).

## Convention

- The package-level `__all__` in every `chattice` package/module **is** the
  public API. Everything listed below is deliberate: it is either documented in
  an [architecture doc](architecture/overview.md) or in the package docstring.
- Deep submodule paths (`chattice.cards.serialization.from_dict`, …) are
  **not** public API, with the explicit exceptions in
  [Compatibility notes](#compatibility-notes).
- `Since` refers to the development phase that introduced the symbol.
  Phases 1–2 shipped together as v0.2.0 (initial import); later phases map to
  the CHANGELOG versions (0.3.0 … 0.11.0).

## Beta stability tiers

The supported surface is divided explicitly; importing a package does not blur
these promises:

1. **Stable beta surface.** Every symbol exported through a stable package's
   `__all__`, plus the documented members below, is frozen from the first
   public beta. It may grow additively before 1.0, but existing names,
   signatures, and semantics do not change incompatibly.
2. **Experimental.** `chattice.experimental` and its subpackages can change or
   disappear without a compatibility promise. Preview feature flags do not by
   themselves make an experimental Google feature stable.
3. **Raw / advanced.** `Bot.raw_client` and event `.raw` payloads expose the
   official Google client and wire data. They are deliberate escape hatches,
   but their breadth and evolution follow Google's SDK/schema rather than the
   stable Chattice facade contract.

## `chattice` (top level)

| Symbol        | Purpose                                                | Since |
| ------------- | ------------------------------------------------------ | ----- |
| `Dispatcher`  | Engine entry point: observers, middleware, DI | P1    |
| `Router`      | Handler tree for observers, commands, dialogs, forms    | P1    |
| `F`           | Magic filter DSL                                        | P1    |
| `__version__` | PEP 440 package version                                 | P1    |

## `chattice.dispatcher`

| Symbol         | Purpose                                    | Since |
| -------------- | ------------------------------------------ | ----- |
| `Dispatcher`   | Async dispatch engine (canonical home)     | P1    |
| `Router`       | Routing tree (canonical home)              | P1    |
| `EventObserver`| Primitive for observer/update registration | P1    |

## `chattice.events`

| Symbol                | Purpose                                            | Since |
| --------------------- | -------------------------------------------------- | ----- |
| `Event`               | Base domain event (frozen, slotted)                | P1    |
| `MessageEvent`        | Chat message; contextual `reply()` and lossless read metadata | P1/DX |
| `CommandEvent`        | Slash, quick, or message-action command            | P1    |
| `CommandKind`         | Typed Google-native command family                 | P13+  |
| `ActionEvent`         | Card click / interaction                           | P1    |
| `ActionSource`        | Proven message/dialog/App Home action surface      | P13+  |
| `AddedToSpaceEvent`   | Bot added to space                                 | P1    |
| `RemovedFromSpaceEvent`| Bot removed from space                             | P1    |
| `UnknownEvent`        | Forward-compatible unknown envelope fallback       | P1    |
| `ErrorEvent`          | Error-observer payload                             | P1    |
| `MessageRef`          | Typed message reference                            | P2    |
| `SpaceRef`            | Typed space reference with zero-fetch `send()`     | P2/DX |
| `ThreadRef`           | Typed thread + optional parent-space reference with `send()` | P2/DX |
| `UserRef`             | Typed user reference                               | P2    |
| `FormInputs`          | Form input mapping (`formInputs`)                  | P2    |
| `FormValue`           | Union of typed form input values                   | P2    |
| `StringInput`         | Single-line text input value                       | P2    |
| `DateInput`           | Date picker value                                  | P2    |
| `DateTimeInput`       | Date+time picker value                             | P2    |
| `TimeInput`           | Time picker value                                  | P2    |
| `UnknownFormInput`    | Forward-compatible form input fallback             | P2    |
| `DialogEventType`     | Dialog lifecycle type (submit/cancel)              | P2    |
| `DialogMetadata`      | Dialog metadata on interactions                    | P2    |
| `TimeZone`            | Normalized timezone value (id + offset)            | P2    |
| `AppHomeEvent`        | App Home / submit-form envelope                    | P2    |
| `FormSubmitEvent`     | App Home form submission                           | P2    |
| `WidgetUpdatedEvent`  | Widget-updated envelope                            | P2    |

## `chattice.filters`

| Symbol          | Purpose                                             | Since |
| --------------- | --------------------------------------------------- | ----- |
| `F`             | Magic filter DSL (canonical home)                   | P1    |
| `MagicExpression` | `F.x == y` intermediate expression                | P1    |
| `MagicField`    | `F.field` attribute access                          | P1    |
| `Filter`        | Async predicate protocol                            | P1    |
| `BaseFilter`    | Convenience base class                              | P1    |
| `FilterLike`    | Type alias (predicate or value)                     | P1    |
| `FilterValue`   | Type alias for filterable values                    | P1    |
| `MagicField.regexp(pattern, flags=)` | Python-regex routing, `re.match` semantics | 0.14.0b5 |

## `chattice.middleware`

| Symbol          | Purpose                                             | Since |
| --------------- | --------------------------------------------------- | ----- |
| `Middleware`    | Structural protocol for dispatch middleware         | P1    |
| `BaseMiddleware`| Convenience base class                              | P1    |
| `MiddlewareLike`| Type alias                                          | P1    |
| `NextHandler`   | Type alias for the `handler` argument               | P1    |

## `chattice.exceptions`

| Symbol                     | Purpose                                        | Since |
| -------------------------- | ---------------------------------------------- | ----- |
| `ChatticeError`            | Base exception for all framework errors        | P1    |
| `StopPropagation`          | Halt routing after the current handler         | P1    |
| `SkipHandler`              | Skip to the next matching handler              | P1    |
| `RoutingControl`           | Type union of routing control exceptions       | P1    |
| `RoutingError`             | Dispatch-time routing failure                  | P1    |
| `FilterError`              | Filter evaluation failure                      | P1    |
| `InvalidHandlerError`      | Handler registration/signature violation       | P1    |
| `ContextConflictError`     | Duplicate data-key injection in a handler      | P1    |
| `DependencyResolutionError`| Handler dependency plan failure                | P1    |
| `RouterConfigurationError` | Router misconfiguration                        | P1    |

## `chattice.adapters.google_chat`

| Symbol                     | Purpose                                           | Since |
| -------------------------- | ------------------------------------------------- | ----- |
| `GoogleInteractionAdapter`| Pure adapter: decoded Google payload → domain event | P2   |
| `parse_interaction`        | Decode + normalize a raw interaction              | P2    |
| `GoogleInteractionError`   | Base adapter error                                | P2    |
| `InvalidInteractionPayload`| Malformed interaction payload                     | P2    |
| `UnsupportedEnvelopeError` | Unknown envelope family                           | P2    |
| `ConflictingEnvelopeError` | Ambiguous/multi-family envelope                   | P2    |

## `chattice.transports.http`

| Symbol                  | Purpose                                             | Since |
| ----------------------- | --------------------------------------------------- | ----- |
| `IncomingRequest`       | Normalized HTTP interaction request                 | P3    |
| `IncomingRequestVerifier`| Request verification protocol                      | P3    |
| `GoogleTokenVerifier`   | google-auth-based Google token verification         | P3    |
| `MockVerifier`          | Test verifier (accepts anything unless reject=True) | P3    |
| `InteractionResponse`   | Response model (text / cards / dialogs / errors)    | P3    |
| `ResponseState`         | Response state machine (double-response guard)      | P3    |
| `InteractionContext`    | HTTP-only verified request/response + 30s deadline  | P3    |
| `HTTPInteractionAdapter`| Web-framework-neutral ingress adapter               | P3    |
| `SYNC_RESPONSE_DEADLINE`| Documented 30-second sync response limit (constant) | P3    |
| `HTTPInteractionError`  | HTTP ingress error base                             | P3    |
| `VerificationError`     | Token verification failure                          | P3    |
| `DoubleResponseError`   | Sync response after ack or repeated send            | P3    |

## `chattice.transports.pubsub`

| Symbol               | Purpose                                            | Since |
| -------------------- | -------------------------------------------------- | ----- |
| `PubSubPushAdapter`  | CloudEvent envelope → interaction event            | P9    |
| `PubSubEnvelopeError`| Pub/Sub envelope decoding error                    | P9    |
| `decode_message_data`| Decode + base64-decode the CloudEvent payload      | P9    |

## `chattice.integrations.fastapi`

| Symbol                        | Purpose                                  | Since |
| ----------------------------- | ---------------------------------------- | ----- |
| `create_chat_router`          | Chat HTTP interactions router            | P3    |
| `create_pubsub_router`        | Pub/Sub push router (204 ack)            | P9    |
| `create_workspace_events_router`| Workspace Events push router           | P9    |

## `chattice.client`

| Symbol                         | Purpose                                        | Since |
| ------------------------------ | ---------------------------------------------- | ----- |
| `Bot`                          | Async outgoing Chat API client                 | P4    |
| `MessageReplyOption`           | Reply semantics (in_thread, threaded reply)    | P4    |
| `ChatAPIError`                 | Wrapped Chat API error base                    | P4    |
| `ChatInvalidArgumentError`     | Wrapped 400-class error                        | P4    |
| `ChatPermissionDeniedError`    | Wrapped 403-class error                        | P4    |
| `ChatNotFoundError`            | Wrapped 404-class error                        | P4    |
| `ChatRateLimitError`           | Wrapped 429-class error                        | P4    |
| `ChatServiceUnavailableError`  | Wrapped 503-class error                        | P4    |
| `ChatUnauthenticatedError`     | Wrapped 401-class error                        | P4    |
| `wrap_api_error`               | Error mapping helper (SDK error → hierarchy)   | P4    |
| `CredentialsProvider`          | Credential protocol — compat re-export (P8)    | P4/P8 |
| `Bot.upload_attachment()`      | USER-auth media upload (`InputFile` → `UploadedAttachment`) | 0.14.0b5 |
| `Bot.download_attachment()`    | Media download (USER or APP; bytes or Path)    | 0.14.0b5 |
| `Bot.get_attachment()`         | Attachment metadata (APP auth + chat.bot)      | 0.14.0b5 |
| `Bot.send_message(..., attachments=)` | Create with uploaded/local attachments  | 0.14.0b5 |

## `chattice.cards`

| Symbol              | Purpose                                         | Since |
| ------------------- | ----------------------------------------------- | ----- |
| `Card`              | Cards v2 top-level facade                       | P5    |
| `CardHeader`        | Card header facade                              | P5    |
| `Section`           | Card section facade                             | P5    |
| `TextParagraph`     | Text widget                                     | P5    |
| `Divider`           | Divider widget                                  | P5    |
| `ButtonList`        | Button list widget                              | P5    |
| `Button`            | Button widget                                   | P5    |
| `Action`            | onClick action facade                           | P5    |
| `OpenLink`          | openLink action facade                          | P5    |
| `TextInput`         | Text input widget                               | P5    |
| `SelectionInput`    | Selection input widget                          | P5    |
| `DateTimePicker`    | Date/time picker widget                         | P5    |
| `Dialog`            | Dialog body facade                              | P6    |
| `ActionStatus`      | actionResponse status facade                    | P6    |
| `ActionStatusCode`  | Status codes (`OK`, `INVALID_ARGUMENT`)         | P6    |
| `ButtonInteraction` | `OPEN_DIALOG` interaction constant              | P6    |
| `Validation`        | Input validation facade (character limit/type)  | P6    |
| `TextInputType`     | Input type constants                            | P6    |
| `Image`             | HTTPS-hosted picture widget (URL-only)          | 0.14.0b5 |

## `chattice.media` (new)

| Symbol                    | Purpose                                       | Since |
| ------------------------- | --------------------------------------------- | ----- |
| `InputFile`               | Canonical local file model (`from_path`/`from_bytes`) | 0.14.0b5 |
| `UploadedAttachment`      | Upload result scoped to one Space             | 0.14.0b5 |
| `AttachmentRef`           | Typed inbound attachment metadata             | 0.14.0b5 |
| `AttachmentSource`        | `UPLOADED_CONTENT` / `DRIVE_FILE`             | 0.14.0b5 |
| `MAX_ATTACHMENT_SIZE_BYTES` | Documented 200 MB upload ceiling            | 0.14.0b5 |

## `chattice.fsm`

| Symbol             | Purpose                                           | Since |
| ------------------ | ------------------------------------------------- | ----- |
| `State`            | Named FSM state                                   | P7    |
| `StatesGroup`      | State group container                             | P7    |
| `FSMContext`       | Per-user/per-space state context                  | P7    |
| `StorageKey`       | Scoped storage key (user/space/thread)            | P7    |
| `FSMStrategy`      | Key strategy enum (default `USER_IN_SPACE`)       | P7    |
| `BaseStorage`      | Storage protocol                                  | P7    |
| `MemoryStorage`    | In-memory storage                                 | P7    |
| `RedisStorage`     | Redis storage (lazy import, `chattice[redis]`)  | P7    |
| `StateFilter`      | Filter matching current state                     | P7    |
| `FSMError`         | FSM error base                                    | P7    |

## `chattice.auth`

| Symbol                            | Purpose                                   | Since |
| --------------------------------- | ----------------------------------------- | ----- |
| `CredentialsProvider`             | Credential protocol (canonical home)      | P8    |
| `ServiceAccountCredentialsProvider`| Lazy service-account credentials         | P8    |
| `UserCredentialsProvider`         | User credentials with lazy refresh        | P8    |
| `DelegatedUserCredentialsProvider`| Domain-Wide Delegation user auth (`with_subject`) | 0.14.0b5 |
| `AuthMode`                        | Auth mode enum (app / user)               | P8    |
| `CHAT_BOT_SCOPE`                  | Documented `chat.bot` OAuth scope         | P8    |

## `chattice.capabilities`

Removed before beta: the combined `Capability` /
`Capabilities` / `CapabilityMatrix` family. Migration: three separate
questions → three types ([capabilities](architecture/capabilities.md)).

| Symbol                  | Purpose                                                    | Since |
| ----------------------- | ---------------------------------------------------------- | ----- |
| `ResponseCapabilities`  | Ingress response channel: transport + concrete event       | P13+  |
| `ResponseCapability`    | SYNC_RESPONSE, DIALOGS, APP_HOME, CARD_UPDATE_*, UPDATE_WIDGET | P13+ |
| `OutboundCapabilities`  | Outbound Bot operations by credential kind                 | P13+  |
| `OutboundCapability`    | MESSAGE_CREATE, MESSAGE_UPDATE, USER_IMPERSONATION         | P13+  |
| `PreviewCapabilities`   | Explicit immutable Developer Preview enrollment            | P13+  |
| `PreviewFeature`        | Developer Preview Google features (stability flags)        | P13+  |
| `can_open_dialog`       | One dialog predicate shared by capabilities + serializer   | P13+  |
| `CapabilityNotSupported`| Runtime guard exception (fail before network)              | P8    |

## `chattice.workspace_events`

| Symbol                 | Purpose                                           | Since |
| ---------------------- | ------------------------------------------------- | ----- |
| `EventsDispatcher`     | Independent Workspace resource-event feed         | P13+  |
| `EventsRouter`         | Independent Workspace resource-event router tree  | P13+  |
| `WorkspaceEvent`       | Workspace Events domain model                     | P9    |
| `WorkspaceEventType`   | Documented event type strings                     | P9    |
| `parse_workspace_event`| CloudEvent → `WorkspaceEvent`                     | P9    |
| `WorkspaceEventError`  | Envelope/parse error                              | P9    |

## `chattice.testing`

| Symbol                | Purpose                                        | Since |
| --------------------- | ---------------------------------------------- | ----- |
| `MockBot`             | DI-compatible Bot recorder (no network)        | P11   |
| `EventFactory`        | Typed event builders (no raw Google JSON)      | P11   |
| `FakeChatTransport`   | Fake transport (migrated in P11)               | P4/P11 |
| `assert_card_has_button` | Card assertion helper                       | P11   |
| `assert_card_header`  | Card header assertion helper                   | P11   |
| `set_state_for`       | FSM state seeding helper                       | P11   |

## `chattice.idempotency`

| Symbol                       | Purpose                                    | Since |
| ---------------------------- | ------------------------------------------ | ----- |
| `IdempotencyStorage`         | Storage protocol                           | P10   |
| `MemoryIdempotencyStorage`   | In-memory storage                          | P10   |
| `RedisIdempotencyStorage`    | Redis storage (SET NX EX, single command)  | P10   |

## `chattice.observability`

| Symbol              | Purpose                                      | Since |
| ------------------- | -------------------------------------------- | ----- |
| `ObservabilityHooks`| Per-event observability hooks (additive, fail-isolated) | P10 |

## `chattice.subscriptions`

Not public API. The
`SubscriptionManager` contract is incomplete (no get/update/renew,
payload options, TTL, lifecycle semantics) and has no implementation.

## `chattice.experimental`

The marker package has no direct exports. The distributedproviders, all explicitly outside the stable core/public API; they may change
or disappear without notice. Stable core never imports it. Preview flags that
gate stable parser/router behavior remain in `chattice.capabilities`.

---

## Surfaces new in 0.13.0

| Package | Symbols |
| --- | --- |
| `chattice.actions` | `ActionData`, `ActionDataDecodeError`, `ActionDataFilter` |
| `chattice.forms` | `FormModel`, `FormDecodeError`, `FormFilter` |
| `chattice.cards` | +`AccessoryWidget`, `RawWidget`; `Button.required_widgets` |
| `chattice.fsm` | +`FSMRecord`, `FSMRecordConflict`, `FSMRecordStorage`, `MemoryFSMRecordStorage`, `RedisFSMRecordStorage`, `BaseStorageFromRecord` |
| `chattice.dispatcher` | +`Lifespan`, `LifespanResource` (`Dispatcher.lifespan`) |
| `chattice.transports.http` | +`WidgetAutocomplete`, `RawInteractionResponse` |
| `chattice.transports.pubsub` | +`GooglePubSubVerifier`, `MockPubSubVerifier`, `PubSubPushVerifier` |
| `chattice.client` | `Bot.send_message(card=, accessory_widgets=)`; `async close()` + context manager |
| `chattice.idempotency` | owner-safe `claim/complete/release/renew`, `ClaimResult` |
| `chattice.capabilities` | `ResponseCapabilities`/`OutboundCapabilities`/`PreviewCapabilities`/`PreviewFeature` |

Renamed pre-1.0: `GChatogramError` → `ChatticeError`.

## Additive beta DX members

No package export was added or removed. The following members extend existing
public types:

| Type | Additive member / accepted form | Contract |
| --- | --- | --- |
| `Dispatcher` | `bot=` constructor keyword | Makes one authenticated Bot available to contextual methods and ordinary DI; per-call `feed_update(..., bot=...)` remains supported. |
| `SpaceRef` | `send(...)` | Delegates directly to `Bot.send_message(space_ref, ...)`; performs no resource lookup. |
| `ThreadRef` | `space`; `send(...)` | Parsed threads retain their known parent. Sends delegate once to `Bot.send_message(..., thread=thread_ref)`; a missing parent fails locally. |
| `MessageEvent` | `reply(...)` | Sends to the known space/thread with `REPLY_OR_FAIL`; missing context fails locally. |
| `MessageEvent` | `attachments`, `annotations`, `mentions`, `quote`, `reaction_summaries`, `is_private`, `is_silent` | Deep immutable, lossless views over the preserved Google message payload; no read or write service call. |
| `ActionData` | `function=` subclass keyword / `.function` | Binds the typed model to Google's existing action function discriminator. |
| `Button` | `action=ActionData(...)` | Encodes the bound function plus flat Google parameters. The existing string `action=` + `parameters=` form is unchanged. |

`chattice.experimental.ai` subpackage contains optional integration
contracts (agent request/response, tool policy, a provider adapter). It
is experimental and outside the stable API; it is not part of the
stable inventory below.

## Compatibility notes

Audited 2026-08-15 against the full test suite, mypy, ruff, and the strict
mkdocs build.

### Removed exports

The pre-beta `chattice.ai` package was removed. Migrate imports tothe stable public API. No accidental exports remain at package level.

### Deliberate internal-but-public-by-convention (kept, not in package `__all__`)

These live at deep submodule paths. They are imported by tests/examples and
are part of the de-facto contract, but are **not** part of the recommended
public surface:

| Path                                              | Symbols                                        | Note |
| ------------------------------------------------- | ---------------------------------------------- | ---- |
| `chattice.dispatcher.dependency`                | `HandlerPlan`, `HandlerCallback`, `ParameterPlan`, `build_handler_plan` | DI plan contract, asserted in tests |
| `chattice.dispatcher.handler`                   | `HandlerObject`                                | Internal handler wrapper |
| `chattice.dispatcher.middleware`                | `MiddlewareManager`                            | Internal middleware chain |
| `chattice.fsm.states`                           | `StatesGroupMeta`                              | Metaclass behind `StatesGroup` |
| `chattice.cards.serialization`                  | `from_dict`, `to_dict`                         | Card JSON round-trip, used by tests |
| `chattice.client.credentials`                   | `CredentialsProvider`                          | Documented Phase 4 compat re-export (canonical home `chattice.auth`) |
| `chattice.testing.fake_transport`               | `FakeChatTransport`                            | Pre-P11 import path kept working |
| `chattice.adapters.google_chat.exceptions`      | `InvalidInteractionPayload` et al.             | Deep error paths mirror package exports |

### Module imports visible outside `__all__` (not exports)

`chattice.middleware.Event`, `chattice.transports.pubsub.Event` and
`chattice.transports.pubsub.parse_interaction` are ordinary module imports
used inside the module body. They are excluded from `__all__`, so
`from … import *` is controlled; they are not part of the public API and
should not be imported from these paths.

### Lazy imports

`chattice.fsm.RedisStorage` is resolved through a module `__getattr__` so
the `redis` dependency stays optional (`chattice[redis]` extra). The symbol
is in `__all__` and importable; importing it without the extra installed
raises the underlying `ImportError`.

### Namespaces with no exports

- `chattice.experimental` — no direct exports by design; its `ai` subpackage is
  an explicitly unstable integration surface.
- `chattice.adapters`, `chattice.transports`, `chattice.integrations` —
  aggregator namespaces with docstring-only bodies.
