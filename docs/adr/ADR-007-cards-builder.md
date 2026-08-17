# ADR-007: Independent typed Cards v2 builder

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

Cards v2 is a large nested schema with widget-specific constraints and fields
whose availability depends on host surface or release status. Generated models
are complete but verbose; a framework builder should be ergonomic without
inventing unsupported combinations.

## Decision

Cards form an independent, typed builder layer that serializes to official
Google models/dictionaries at the boundary. Pydantic v2 validates constraints
where it adds useful diagnostics. Action callbacks map the public action name
to Google's `function`; action parameters remain string key/value pairs and
form inputs remain a separate event field.

The stable builder exposes only documented stable Chat features. `RawWidget`
and official-model escape hatches cover new fields. Capability validation is
surface-aware and may be deferred until attachment when context is required.

## Consequences

Common card construction is concise and invalid combinations fail early. The
builder has a meaningful maintenance burden and must be continuously checked
against official Cards v2 docs. It cannot promise identical support across
messages, dialogs, and App Home.

## Alternatives considered

- Generated models only: faithful but poor developer ergonomics.
- Untyped dictionaries: flexible but errors arrive from Google at runtime.
- A generic UI component system: likely to imply cross-platform guarantees the
  project cannot provide.

## Sources

[Cards v2 reference](https://developers.google.com/workspace/chat/api/reference/rest/v1/cards),
[design interactive cards](https://developers.google.com/workspace/chat/design-interactive-card-dialog),
[troubleshoot cards](https://developers.google.com/workspace/chat/troubleshoot-cards).

