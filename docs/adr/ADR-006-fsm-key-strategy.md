# ADR-006: Explicit FSM key strategy

- Status: Accepted
- Date: 2026-08-13 (accepted with Phase 7, 2026-08-14)
- Owners: maintainers

## Context

Conversation state can reasonably be scoped by user, space, thread, or a
combination. Google resource names are strings and events do not always contain
all dimensions. A hidden key choice causes state leakage or surprising sharing.

## Decision

FSM storage uses a structured `StorageKey` with user, space, and thread
dimensions (no app dimension — implemented as shipped). `FSMStrategy`
explicitly selects the required dimensions; the default is `USER_IN_SPACE`
(user + space, thread when present); applications opt into `USER` or `SPACE`.
Missing required dimensions yield no key: reads degrade to None/{} and
mutations raise `FSMError`.

Storage contracts are honest about concurrency: MemoryStorage serializes per
key with process-local asyncio locks; RedisStorage relies on per-command
atomicity only (`update_data` is NOT cross-process — no Lua). Expiration
support is not implemented. In-memory storage is for tests/development;
Redis support is the optional `chattice[redis]` extra, implemented in
Phase 7.

## Consequences

State isolation is visible and testable. Apps must choose deliberately when
thread semantics matter. Migrations between strategies need an application
plan; the framework cannot infer intent.

## Alternatives considered

- Always key by user: leaks state across spaces.
- Always key by user/space/thread: fragments direct-message flows and fails
  when thread data is absent.
- Accept arbitrary strings as keys: flexible but unsafe and non-portable.

## Sources

[Google Chat Event schema](https://developers.google.com/workspace/chat/api/reference/rest/v1/Event),
[aiogram FSM strategy](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/strategy.html),
[aiogram storage](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/storages.html).

