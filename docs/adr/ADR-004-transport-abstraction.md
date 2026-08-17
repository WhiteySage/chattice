# ADR-004: Envelope-based transport abstraction

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

Google Chat delivers synchronous HTTP interactions and asynchronous Pub/Sub
interactions, while Workspace Events uses CloudEvents and Pub/Sub for resource
changes. These modes differ in payload envelope, verification, deadlines, and
available responses. Dispatch should not depend on a web framework.

## Decision

Ingress integrations produce an `InteractionEnvelope` containing payload,
transport metadata, verification state, and a `ResponseChannel`. A dedicated
adapter maps the envelope to domain events. The core dispatcher consumes only
domain events plus explicit context/capabilities.

HTTP, Pub/Sub interaction, and Workspace Events adapters remain distinct. They
may share utilities but never erase differences in acknowledgement or response
semantics. The core has no FastAPI or Starlette dependency.

## Consequences

Synthetic tests are simple and integrations can evolve independently. Adapter
code is more explicit. Transport capability checks prevent impossible actions
such as opening a dialog from Pub/Sub interaction delivery.

## Alternatives considered

- Pass HTTP requests into handlers: couples every handler to deployment.
- Normalize all delivery modes into one dictionary: hides critical differences.
- Make Pub/Sub merely an HTTP retry queue: does not match Google's contracts.

## Sources

[receive and respond to interactions](https://developers.google.com/workspace/chat/receive-respond-interactions),
[Pub/Sub interaction endpoint](https://developers.google.com/workspace/chat/quickstart/pub-sub),
[Workspace Events for Chat](https://developers.google.com/workspace/events/guides/events-chat).

