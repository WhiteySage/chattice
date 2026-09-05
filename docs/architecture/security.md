# Security

This page describes the framework's security controls and threat boundaries.
Each control names its enforcing mechanism and corresponding test.

## Incoming request verification

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

Signature, expiry, and audience are validated by `google-auth`. HTTPS
endpoint audiences use `verify_oauth2_token` with Google OAuth2 certificates;
project-number audiences use `verify_token` with Chat service-account
certificates. Issuer and service-account identity checks follow the selected
strategy. `MockVerifier`
exists for tests and local development only — never wire it into production.
Pub/Sub push endpoints are verified by default as well: the push routers
require a `PubSubPushVerifier` or an explicit `allow_unverified=True`
(see [pubsub](pubsub.md)).

## Logging and credential boundaries

At normal logging levels, framework errors identify exception classes rather
than exception messages. Parse and verification failures use stable diagnostic
fields instead of serializing the incoming payload. HTTP error responses do
not expose exception details.

DEBUG runtime and pull-runner logs attach tracebacks, including exception
messages and chained exceptions. Application errors can contain credentials or
form values, so DEBUG output is not a redacted channel. Avoid placing sensitive
values in exceptions and enable DEBUG only where its output is appropriate.
See [debugging](../guides/debugging.md).

A Bot caches successful credential resolution separately for each identity;
failed provider calls are not cached. Token storage and OAuth consent belong
to the application. The framework does not deliberately format credentials
into its diagnostics.

Observability hooks receive the original event, context, result, and exception.
They can access `.raw`; applications must select which fields to export. Hook
failures log the hook name without serializing those values.

## Action parameters (strings only)

`ActionEvent.parameters` arrives from Google as key/value strings. The
framework stores a shallow immutable snapshot
(`MappingProxyType(dict(...))`) and **never auto-deserializes** values —
a parameter value like `"true"` or `"42"` stays a string; the application
interprets it. On the outbound side the card `Action.parameters` facade is
`Mapping[str, str]` by construction, so nothing richer than strings can be
put on the wire. Typed `ActionData` filters may explicitly validate these strings into an
application model; this is separate from the lossless event mapping.

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

Known Card fields are validated through the typed facades and Google SDK
protos. `Card.from_dict()` also preserves unknown JSON fields and represents
unsupported widgets with `RawWidget`; unknown fields do not necessarily fail
parsing. This lossless JSON path is distinct from protobuf validation. See
[cards](cards.md).

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

HTTP and push boundary logs report exception types without echoing details to
the caller. DEBUG runtime tracebacks follow the logging policy above. A handler failure on a sync
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
