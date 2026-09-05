# ADR-013: Remove the legacy outbound facade

- Status: Accepted
- Date: 2026-09-03
- Owners: maintainers

## Context

ADR-012 froze the pre-0.2 outbound surface (`Bot.send_message` and the
other `Bot` convenience methods, `bot.raw_client`,
`OutboundCapability`/`OutboundCapabilities`) as a compatibility facade
that mapped one-way onto the operation registry. After the registry →
executor → identity → resource architecture shipped in 0.2.0, the facade
was dead weight: one operation had two documented spellings, the
compatibility wrappers kept the old identity-selection semantics (silent
APP-first resolution, APP→USER download fallback) in tension with the
explicit-identity rule, and every new resource had to explain itself
twice.

## Decision

Remove the legacy surface in 0.3.0 (pre-1.0 minor bump per ADR-011):

- All `Bot` convenience methods (`send_message`, `update_message`,
  `get_message`, `delete_message`, `get_space`, `list_spaces`,
  `add_member`, `get_member`, `list_members`, `remove_member`,
  `upload_attachment`, `download_attachment`, `get_attachment`) are
  removed. Every operation lives on the identity-bound resource
  clients (`bot.app.*` / `bot.user.*`) and runs through the single
  executor path.
- `Bot.raw_client` is removed; `await bot.raw.app()` /
  `await bot.raw.user()` is the only raw access.
- `Bot.capabilities` and the `OutboundCapabilities`/`OutboundCapability`
  matrix are removed; the `OperationRegistry` is the single preflight.
- Contextual helpers (`MessageEvent.reply()`, `ThreadRef.send()`,
  `SpaceRef.send()`) are NOT legacy: they are documented DX and now
  delegate to `bot.app.messages.create(...)` instead of the removed
  wrapper. Their reply-option defaults are unchanged.
- A zero-credential call now fails closed with `CapabilityNotSupported`
  before any client construction or transport work, for both
  identities (an invalid request never reaches the network).

## Consequences

- Easier: one operation → one documented spelling → one execution path.
  Migration is a mechanical rename covered by the stability migration
  table.
- Harder: 0.2.x callers using the convenience methods must migrate in
  the 0.3.0 upgrade; the breaking change is called out in CHANGELOG.
- Intentionally unsupported: no compatibility shims, no silent
  identity fallbacks, no second preflight implementation.

## Alternatives considered

- Keep the facade until 1.0 (ADR-012's original plan). Rejected: the
  dual spelling had already caused duplicated tests and divergent
  guard order between the two paths; the facade's identity semantics
  contradicted ADR-012's explicit-identity rule.
- Soft-deprecate with warnings for one cycle. Rejected: a beta-stage
  library (ADR-010) gains little from a deprecation cycle the 0.2.0
  release notes already announced, and carrying both paths doubles the
  documented surface.

## Sources

- ADR-011 (versioning policy), ADR-012 (curated outbound facade).
- `docs/stability.md` — the 0.3.0 migration table.
