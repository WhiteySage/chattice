# Transports

Status: **Proposed**. See [ADR-004](../adr/ADR-004-transport-abstraction.md) and
[ADR-008](../adr/ADR-008-sync-async-responses.md).

## Boundary

A transport receives bytes/messages and produces a verified, decoded envelope.
It does not parse domain events or route handlers. An adapter converts the
envelope into a domain event; the dispatcher consumes the domain event.

Proposed ingress contract:

```python
@dataclass(frozen=True)
class InteractionEnvelope:
    payload: Mapping[str, object]
    delivery: DeliveryMetadata
    capabilities: Capabilities


class EventAdapter(Protocol):
    def parse(self, envelope: InteractionEnvelope) -> Event: ...
```

Server lifecycle is not part of core `Transport`. FastAPI/Starlette integrations
compose an endpoint around verifier -> decoder -> adapter -> dispatcher.

## HTTP

HTTP is the v0.1 transport. The integration must:

1. enforce POST/HTTPS deployment assumptions;
2. verify the Google bearer token with an injected verifier;
3. bound and decode JSON;
4. normalize documented envelope variants;
5. dispatch within a tracked 30-second response deadline;
6. serialize exactly one valid synchronous response;
7. preserve original exceptions for logging without leaking payload secrets.

The core does not depend on FastAPI. A Starlette-level adapter is sufficient;
FastAPI composition can return an `APIRouter` as an optional convenience.

## Pub/Sub interaction endpoint

Pub/Sub is Phase 8. Its envelope is asynchronous and cannot expose dialog or
synchronous card-update capabilities. A handler can be shared only when the
domain semantics and requested response behavior overlap.

Pub/Sub interaction events and Workspace Events both use Pub/Sub but have
different envelopes and meanings. A discriminator selects the correct adapter;
transport similarity is not domain equivalence.

## Delivery and deadlines

`DeliveryMetadata` can include received time, deadline, verified audience,
transport name, and documented delivery identifier if one exists. It must not
invent an ID from a payload hash.

The dispatcher records latency but does not automatically cancel application
work at 30 seconds. HTTP policy may warn or set a configurable timeout; killing
a handler can leave side effects in an unknown state. Slow workflows should
respond promptly and continue through explicit application infrastructure.

## Duplicates

Because HTTP retries can repeat an interaction and no stable interaction ID is
documented, a generic exactly-once layer is impossible. A later idempotency
middleware can accept an application key extractor and storage, but must make
its guarantee and collision domain explicit.

