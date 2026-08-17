# Security

A written audit of the framework's security posture, control by control.
Each item names the phase that implemented it, the enforcing mechanism, and
the test that pins it. The audit closes with the threat boundaries — what the
framework deliberately does NOT protect.

## Incoming request verification (Phase 3)

Every inbound HTTP interaction is verified before parsing: the FastAPI
integration (`create_chat_router`) calls the configured
`IncomingRequestVerifier` and returns **401** on `VerificationError`
(`tests/test_fastapi_integration.py`). The production verifier is
`GoogleTokenVerifier` ([authentication](authentication.md)), which supports
both documented audience strategies:

| Strategy | Token | Audience | Issuer check |
| --- | --- | --- | --- |
| Project number | Self-signed JWT by the Chat service account | Project number | `chat@system.gserviceaccount.com` |
| Endpoint URL | Google OIDC ID token of the service account | HTTPS endpoint URL | `accounts.google.com` + same service-account email |

Signature, `exp`, `aud`, and certificate selection are delegated to
`google-auth`'s `verify_token` against the Chat certificates URL; the issuer
is checked explicitly per strategy (as the official samples do). `MockVerifier`
exists for tests and local development only — never wire it into production.
Pub/Sub push endpoints are verified by default as well: the push routers
require a `PubSubPushVerifier` or an explicit `allow_unverified=True`
(see [pubsub](pubsub.md)).

## Logging redaction (runtime-enforced)

Framework error logs carry exception CLASSES only — never exception
messages, and boundary parse failures (interaction, Pub/Sub envelope,
Workspace envelope) log stable fields only. Untrusted payloads cannot
reach logs or response bodies; this is pinned by RUNTIME sentinel
tests (`tests/test_log_redaction.py`), not only by the source scan
(F02).

## Credential leakage

- The credentials provider is resolved **once** per `Bot` lifecycle
  (`Bot._resolve_credentials`, guarded by a resolved-flag); a provider
  failure is not cached, so it re-raises instead of silently degrading.
- Credentials never appear in logs. The framework logs error *classes* and
  message payloads, not token material — and this is **pinned by a source
  scan** (`tests/reliability/test_redaction.py`): no `logger.*`/`log.*` call
  in `src/` may reference token-like content (`token`, `authorization`,
  `bearer`, `private_key`, `client_secret`, `refresh_token`). The test runs
  on every CI pass; introducing secret logging is a test failure, not a
  review suggestion.

## Logging redaction

All framework loggers live under `chattice.*` and follow two rules:

1. Never log bearer tokens, credentials, or payload bodies that may contain
   them (pinned by the redaction scan above).
2. Structured, searchable context only: event type, path, latency — never
   request bodies or raw interaction dumps.

Hook failures are logged to `chattice.observability` without the event
payload ([observability](observability.md)).

## Action parameters (strings only)

`ActionEvent.parameters` arrives from Google as key/value strings. The
framework stores a shallow immutable snapshot
(`MappingProxyType(dict(...))`) and **never auto-deserializes** values —
a parameter value like `"true"` or `"42"` stays a string; the application
interprets it. On the outbound side the card `Action.parameters` facade is
`Mapping[str, str]` by construction, so nothing richer than strings can be
put on the wire. No code path deserializes action input into objects.

## Form data (typed FormInputs)

Submitted form values are parsed into the typed union `FormValue`
(`StringInput`, `DateInput`, `DateTimeInput`, `TimeInput`) — an immutable
`FormInputs` mapping from widget name to typed value, with no raw dict
exposure. Unknown future input variants become `UnknownFormInput`: the raw
mapping is retained immutably (frozen `MappingProxyType`) without claiming
semantics — never parsed, never executed.

## URL handling

Card URLs are carried by the `OpenLink` facade (`url: str`) and placed into
the SDK `OpenLink` proto verbatim. The framework performs no URL fetch,
redirect, or scheme rewrite: the URL is exactly what the application
provided, and Google's client performs the open. No framework code ever
fetches application-supplied URLs.

## Card input (SDK proto validation)

Card JSON is (de)serialized exclusively through the SDK's protobuf
`json_format` (`MessageToJson` / `Parse`) — malformed, unknown, or
out-of-range fields fail protobuf validation instead of being interpreted
by hand-written parsers. Card structures are constructed through the typed
facade layer (`chattice.cards`) and round-tripped via protos
(`tests/test_cards_integration.py`).

## Deserialization

All inbound payload decoding is **JSON only**:

- HTTP interactions: `parse_interaction` → strict mapping access, no
  dynamic dispatch on payload structure.
- Pub/Sub envelopes: strict base64 + `json.loads` with explicit error
  classes (`PubSubEnvelopeError`).
- Cards: protobuf `json_format` (above).

There is **no `pickle` and no `eval(` anywhere in `src/`** — verified by
source scan (the same pattern as the redaction test). No inbound data is
ever turned into code or objects via unsafe serialization.

## Dependency injection (name-based)

Handler dependencies resolve from a closed set of keys: typed event classes
(via `isinstance` against framework event types), a fixed alias table
(`event`, `message`, `action`, ...), and the dispatch context mapping
(`data`) that the framework itself populates (injected `state`, `request`,
`response`, `interaction`, `capabilities`). Unknown parameter names with no
default raise `DependencyResolutionError`. Resolution is name-based on known
keys only — there is no registry of arbitrary callables, no dynamic import,
and no code execution from handler annotations (see
[dependency-injection](dependency-injection.md)).

## Exception responses (no internals)

Webhook surfaces return generic status codes with no internals:

| Path | Failure | Response |
| --- | --- | --- |
| `create_chat_router` | verification failed | 401 (empty) |
| `create_chat_router` | unparseable interaction | 400 `{"error": "invalid_interaction_payload"}` |
| `create_chat_router` | handler raised | 500 (empty) |
| pubsub / workspace routers | malformed envelope | 400 (empty) |
| pubsub / workspace routers | handler raised / dedupe storage failed | 500 (empty) |

The full exception is logged server-side (`chattice.http` /
`chattice.push`) — never echoed to the caller. A handler failure on a sync
channel is additionally routed to the error observer, so the app can respond
inside the 30-second window instead of exposing a bare 500.

## Threat boundaries

The framework operates behind the deployment's perimeter. It does NOT
provide:

- **TLS termination** — HTTPS, certificates, and HSTS belong to the hosting
  platform (load balancer, Cloud Run, App Engine); the framework assumes the
  inbound request already arrived over a trusted TLS channel.
- **Application secrets** — service-account JSON, OAuth client IDs, and
  scopes are supplied by the application and stored wherever the
  application stores secrets (Secret Manager, env, vault); the framework
  never persists them.
- **OAuth token storage** — `UserCredentialsProvider` documents that token
  storage and OAuth code acquisition belong to the application
  ([bot-api-client](bot-api-client.md)); the framework only holds in-memory
  credentials for the process lifetime.
- **DDoS/rate defense** — webhook endpoints are plain POST routes; request
  rate limiting, IP allow-listing, and bot management are platform
  concerns.

Anything the framework can verify in-process (signatures, structure, types)
is verified here; anything requiring infrastructure it does not own is
documented as the application's contract.
