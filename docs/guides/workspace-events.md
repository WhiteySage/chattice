# Workspace Events

Workspace Events report Google resource changes. They are not user interaction
events and use a separate parser and router tree.

## Handle an event

```python
from chattice.workspace_events import (
    EventsDispatcher,
    EventsRouter,
    WorkspaceEvent,
    WorkspaceEventType,
)

router = EventsRouter()


@router.workspace_event(WorkspaceEventType.MESSAGE_CREATED)
async def message_created(event: WorkspaceEvent) -> None:
    print(event.subject)


dispatcher = EventsDispatcher()
dispatcher.include_router(router)
```

Supported typed families cover messages, memberships, reactions, and Spaces;
unknown CloudEvent types remain representable through the normalized event.
The parser accepts a CloudEvents 1.0 mapping directly with
`parse_workspace_event()` or a Pub/Sub envelope with
`parse_workspace_envelope()`.

## Receive through FastAPI

```python
from fastapi import FastAPI

from chattice.integrations.fastapi import create_workspace_events_router

app = FastAPI()
app.include_router(
    create_workspace_events_router(
        dispatcher,
        verifier=pubsub_verifier,
        path="/workspace-events",
    )
)
```

The verifier must validate Pub/Sub push identity. Test-only unverified modes
must never be exposed publicly.

## Create the Google subscription

The Google side requires:

1. Enable the Google Workspace Events API and Chat API.
2. Create a Pub/Sub topic in the same Cloud project and grant the documented
   Google Workspace publisher identity access.
3. Create a Workspace Events subscription with the target resource, event
   types (for example `google.workspace.chat.message.v1.created`), Pub/Sub
   topic, and payload options.
4. Create a Pub/Sub push subscription targeting the Chattice endpoint, or
   consume the topic with your own subscriber.
5. Renew/reactivate expiring subscriptions as required by Google.

Subscription creation has its own identity/scope rules and may use user auth
or eligible app auth with one-time administrator approval. Follow Google's
[Create a Google Workspace subscription](https://developers.google.com/workspace/events/guides/create-subscription)
and [scope matrix](https://developers.google.com/workspace/events/guides/auth).

Resource-event handlers have no synchronous Chat interaction response. If a
handler must post to Chat, inject an authenticated `Bot` and call it
imperatively.

Next: [HTTP and Pub/Sub](transports.md).
