# Pub/Sub push ingress

Status: **Implemented** (Phase 9). Google Pub/Sub delivers Chat interactions
(and Workspace Events — see [workspace-events](workspace-events.md)) to a
push endpoint. This page documents the interaction envelope,
`PubSubPushAdapter`, ack semantics, and what the framework deliberately
does NOT do.

## Envelope schema

Pub/Sub push delivers a documented JSON envelope. The Chat interaction JSON
sits inside `message.data` as a base64 string:

| Field | Type | Meaning |
| --- | --- | --- |
| `message.data` | string (base64) | the interaction JSON, decoded by the adapter |
| `message.messageId` | string | Pub/Sub-assigned message identifier |
| `message.publishTime` | string | RFC 3339 publish timestamp |
| `message.attributes` | mapping | user-provided message attributes (unused by the adapter) |
| `subscription` | string | the subscription name that delivered the message |

`PubSubPushAdapter.parse_envelope(payload)` validates the envelope
(`PubSubEnvelopeError`), base64-decodes `message.data` (strict — validate=True),
parses the inner JSON, and runs the normal interaction adapter
(`parse_interaction`). The FULL envelope — not just the inner interaction —
is stored in `event.raw`, so handlers can inspect delivery metadata without
re-parsing.

## Ack semantics

Pub/Sub treats any 2xx status from the push endpoint as an ack. The push
router (`create_pubsub_router`) acks with `204 No Content` after the handler
completes:

- `400` — malformed envelope (non-JSON, invalid base64, invalid interaction).
  Pub/Sub will retry; the logs explain why.
- `500` — handler raised. Delivery retries with Pub/Sub's configured backoff.

## No synchronous responses

Push delivery has no synchronous response channel. The `pubsub` capability
rows are the corresponding HTTP rows minus `SYNC_RESPONSE` and `DIALOGS`
([capabilities](capabilities.md)). Handler return values are ignored by
`create_pubsub_router` — the ack is already on its way. Handlers that must
react use the Chat API asynchronously: `MESSAGE_CREATE` / `MESSAGE_UPDATE`
remain available with app credentials.

## Capabilities

`create_pubsub_router` injects an EMPTY response-channel capability set
(`ResponseCapabilities.resolve(transport="pubsub", event=event)`) into
handler context — the push surface is ack-only, so every response
attempt fails fast via `require()` ([capabilities](capabilities.md)).

## Push auth: verified by default

Google signs push requests with an OIDC JWT in the `Authorization` header
(issuer `accounts.google.com` / the Pub/Sub service account), and
`message.attributes` carries provenance data. `create_pubsub_router`
REQUIRES a `PubSubPushVerifier` (audience/issuer/certificate checks,
off-loop) or an explicit `allow_unverified=True` for local/test
environments — the router refuses to be created without either
(secure-by-default, F07).

## Pull delivery: implemented (streaming pull)

`dispatcher.run_pubsub(subscription, bot=bot)` runs streaming pull via
`google-cloud-pubsub` (the `pubsub` extra) through the SAME
parser → Dispatcher pipeline as the HTTP router. Semantics:

- one explicit per-delivery attempt state machine: subscription-
  namespaced dedupe key, owner-checked claim (COMPLETED → ACK, ACTIVE →
  NACK, FIRST → process), lease renewal tied to the attempt,
  complete-then-ACK exactly once — a delivery is never both ACKed and
  NACKed (F03);
- handler answers go outbound via `Bot` (`str` → send, `Card` →
  update/send); `Dialog`/`ActionStatus` answers raise
  `CapabilityNotSupported` and the space is told (B7);
- `run()` races the stop event against the streaming-pull future and
  surfaces unrecoverable subscriber failures; shutdown cancels the pull
  future and drains scheduled attempts.

Streaming pull is NOT Telegram-style long polling: it is a persistent
subscriber stream with Pub/Sub's own acknowledgement protocol — see
[aiogram comparison](../aiogram-comparison.md).
