# ADR-003: Raw Google model escape hatches

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

Google Chat evolves independently of the framework. A typed abstraction cannot
predict every new field, preview feature, or generated client capability.
Applications must not wait for a framework release to use supported Google
functionality.

## Decision

Domain events expose opaque raw payload access, and outbound APIs accept
official generated request/resource models through clearly named advanced
entry points. Typed convenience APIs preserve unknown fields when round-trips
are supported. Raw entry points never silently weaken auth, capability, or
response-channel validation.

No framework-owned model pretends to be wire-complete. Experimental Google
features live outside the stable namespace until their contract is stable.

Phase 2 defines incoming `event.raw` as a deep snapshot of the complete decoded
mapping. The frozen event prevents reassignment but does not recursively freeze
the opaque raw value. Outbound generated-model escape hatches remain proposed
until their implementation phase.

## Consequences

Advanced users retain full platform reach and new fields degrade gracefully.
The public API must distinguish portable framework semantics from direct Google
semantics. Compatibility tests need real official sample payloads and generated
model serialization fixtures.

## Alternatives considered

- Hide raw models: cleaner surface, unacceptable platform lag.
- Expose only raw models: sacrifices framework ergonomics and stability.
- Copy Google's full schema: duplicates a generated client and drifts quickly.

## Sources

[official Python client](https://googleapis.dev/python/google-apps-chat/latest/),
[Google Chat REST reference](https://developers.google.com/workspace/chat/api/reference/rest).
