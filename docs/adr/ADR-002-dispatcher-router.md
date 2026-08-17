# ADR-002: Dispatcher, router, and observer split

- Status: Accepted
- Date: 2026-08-14
- Owners: maintainers

## Context

The desired developer experience resembles aiogram, but Google Chat event
semantics and response modes differ from Telegram. Registration, matching,
middleware, dependency injection, propagation, and application lifecycle need
separate responsibilities.

## Decision

`Router` owns named event observers and composes child routers. An observer owns
ordered handlers for one event category. `Dispatcher` is the root router and
dispatch entry point. Each handler has filters and flags; middleware wraps a
resolved handler plan. Dependency injection resolves explicit event/context
data by annotation/name and reports ambiguity. The default propagation rule is
first successful matching handler, with any fan-out behavior requiring an
explicit policy.

Router ownership is a single-parent acyclic tree traversed pre-order and
depth-first. Event selection uses a global specific-observer pass followed by a
generic `event` fallback. `SkipHandler` continues with the next candidate and
`StopPropagation` ends search; both are dedicated non-error control flow. One
post-filter middleware layer wraps invocation, with parent middleware wrapping
descendant middleware. Error observers receive an `ErrorEvent` once and do not
recurse.

Phase 1 exposes `feed_update()` for synthetic domain events only. Lifecycle and
transport startup remain outside dispatch.

## Consequences

Nested feature routers stay reusable, dispatch is transport-neutral, and tests
can exercise routing without Google credentials. Attached router instances
cannot be shared across parents. Ordered matching and inclusion order are
observable and therefore covered by compatibility tests.

## Alternatives considered

- One global handler registry: simpler initially, poor modular composition.
- Reuse an HTTP router: route paths do not model event/filter semantics.
- Broadcast to every matching handler: convenient for event buses but unsafe
  as a bot default because it can duplicate side effects and responses.

## Sources

[aiogram Dispatcher](https://docs.aiogram.dev/en/latest/dispatcher/dispatcher.html),
[routers and observers](https://docs.aiogram.dev/en/latest/dispatcher/router.html),
[middleware](https://docs.aiogram.dev/en/latest/dispatcher/middlewares.html).
