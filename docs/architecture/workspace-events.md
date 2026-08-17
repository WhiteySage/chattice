# Workspace Events

Status: **Implemented** (Phase 9, corrected in Phase 14 A1). Workspace
Events deliver resource-change notifications (NOT Chat interactions) as
CloudEvents through Pub/Sub push. They have an independent
`EventsRouter`/`EventsDispatcher` runtime; `WorkspaceEvent` is deliberately
not an ordinary `chattice.events.Event`.

## The wire format (official Pub/Sub binding)

Google delivers Workspace Events exclusively as Pub/Sub push messages.
The CloudEvents context attributes travel in `message.attributes` with
`ce-` keys, while base64-decoded `message.data` holds ONLY the event
resource data (or resource names for names-only payloads):

```json
{
  "message": {
    "data": "eyJtZXNzYWdlIjp7Im5hbWUiOiJzcGFjZXMvQUFBL21lc3NhZ2VzL0IifX0=",
    "messageId": "m-2",
    "attributes": {
      "ce-id": "evt-1",
      "ce-source": "//chat.googleapis.com/spaces/AAA",
      "ce-specversion": "1.0",
      "ce-time": "2026-08-15T10:00:00Z",
      "ce-type": "google.workspace.chat.message.v1.created"
    }
  },
  "subscription": "projects/p/subscriptions/s"
}
```

`parse_workspace_envelope(payload)` validates the envelope
(`WorkspaceEventError`: required `ce-id`/`ce-source`/`ce-specversion`/
`ce-type`, specversion `1.0`, `google.workspace.`-prefixed type,
`application/json` datacontenttype, base64+JSON data) and produces a
`WorkspaceEvent` domain event: `event_id`, `source`, `subject`,
`event_time`, `data`, `cloud_type` — with `event_type="workspace_event"`
and the FULL push envelope in `raw`.

`parse_workspace_event(payload)` still accepts a STRUCTURED CloudEvent
(all fields at the top level) for offline use (fixtures, replays, tests) —
a structured CloudEvent POSTed to the push endpoint is NOT a supported
delivery mode and is rejected with 400.

## Type constants and forward compatibility

`WorkspaceEventType` documents the current stable Chat types (verified
2026-08-15 against the official event guides): message
created/updated/deleted, reaction created/deleted, membership
created/updated/deleted, space updated/deleted, space/thread read-state
updated, availability updated, and the subscription lifecycle types
(suspended / expirationReminder / expired).

Parsing requires only the `google.workspace.` prefix — unknown
`google.workspace.*` types (including OUTPUT-ONLY batch variants like
`*.batchCreated` / `*.batchUpdated` / `*.batchDeleted`, which Google
delivers automatically alongside single-resource subscriptions) parse
fine (forward compatibility), so new Google types never break an app;
string filters simply don't match them until the app registers a
handler. NOTE: `WorkspaceEventType` enumerates the SINGLE-RESOURCE
set, not the complete official set — batch types are preserved
through the generic parser and routable by raw string.

## Independent events runtime

`EventsRouter.workspace_event` accepts a string shortcut that filters on the
CloudEvent `type`:

```python
from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    WorkspaceEventType,
)

router = EventsRouter()


@router.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
async def on_created(event: WorkspaceEvent) -> None: ...


@router.workspace_event()  # any google.workspace.* type
async def on_any(event: WorkspaceEvent) -> None: ...


dispatcher = EventsDispatcher()
dispatcher.include_router(router)
await dispatcher.feed_event(event)
```

The interaction `Router` has no `workspace_event` observer, and interaction
`Dispatcher.feed_update()` rejects `WorkspaceEvent`; applications migrating
from the pre-beta snapshot must instantiate this separate runtime and call
`feed_event()` instead. Handlers must be defined at module level (annotation
resolution). The HTTP surface is `create_workspace_events_router` (204 ack,
400 malformed, no sync response channel) and now accepts an
`EventsDispatcher`. The router is secure by default: pass
`verifier=GooglePubSubVerifier(...)` (authenticated push) or an explicit
`allow_unverified=True`; with `idempotency_storage` redeliveries dedupe by
the Pub/Sub message id with claim/complete/release semantics.

## Subscriptions via the Workspace Events API

Subscriptions are created OUTSIDE this framework, through the Workspace
Events REST API. A subscription combines:

- `targetResource` — the resource to watch (e.g. a space);
- `eventTypes` — the `google.workspace.*` types to deliver;
- `notificationEndpoint` — a Pub/Sub topic the app owns (the ONLY
  supported endpoint kind; there is no HTTPS delivery mode);
- `payloadOptions` — payload filtering (full data or names only).

Subscriptions EXPIRE (hours to days) and must be renewed; Google also
sends lifecycle events (`google.workspace.events.subscription.v1.*`) and
recommends querying missed events via `spaces.spaceEvents.get/list` after
outages. The app's push endpoint receives the CloudEvents on the topic.
Subscription lifecycle management is DEFERRED (F14): applications bring
their own client for create/renew; the removed internal prototype is
no longer shipped.

## Workspace Events vs interaction events

Workspace Events describe resource changes (message created/updated/deleted,
space updated, membership changed, reactions, read states). They can be
broad — many spaces, no interaction context — and there is NO synchronous
response: no ack of the user's action, no dialog, no sync card update.
Interaction events are single-request/single-response dialogues (a message
the user typed, a card click) over the HTTP transport. The two ingresses
are isolated end-to-end: separate domain models, adapters, observers,
dispatchers, routers, and tests pin that neither runtime accepts the other
family.
