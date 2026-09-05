# ADR-001: Framework-owned event domain model

- Status: Accepted
- Owners: maintainers

## Context

Google interaction payloads are sparse and vary by event type. Generated API
messages model the public resource API well but do not provide the ergonomic,
stable event vocabulary required by filters, dependency injection, testing,
and multiple ingress families. Google can also add enum values and fields.

## Decision

Adapters create immutable, framework-owned domain events using
`@dataclass(frozen=True, slots=True)`. The base set includes `Event`,
`MessageEvent`, `ActionEvent`, and `UnknownEvent`, plus an `ErrorEvent` used by
dispatch. Base fields are only those common enough to be truthful; subtype
construction validates its own requirements. Every event retains an opaque raw
value. Unknown event types are representable rather than rejected.

Domain events contain no Google SDK values, authentication state, or
transport/delivery metadata. Those enter only through explicit adapter/context
types when supported by sourced requirements. Pydantic
is reserved for untrusted external boundaries rather than framework events.

Interaction events and Workspace Events remain separate ingress families.
Shared concepts may converge only after their semantics are proven equivalent.

## Consequences

Handlers receive a stable API and tests can construct events without generated
protobuf knowledge. Adapters carry mapping work, and raw access plus
compatibility fixtures become mandatory. Frozen events do not recursively
freeze an arbitrary `raw` value. No universal event ID is invented.

## Alternatives considered

- Expose only generated Google types: faithful but tightly coupled and awkward
  for dispatch/testing.
- Use untyped dictionaries: forward-compatible but moves validation failures
  into application code.
- Force every payload into one large model: creates misleading optional fields.

## Sources

[Google Chat Event](https://developers.google.com/workspace/chat/api/reference/rest/v1/Event),
[EventType](https://developers.google.com/workspace/chat/api/reference/rest/v1/EventType),
[Google Chat events overview](https://developers.google.com/workspace/chat/events-overview).
