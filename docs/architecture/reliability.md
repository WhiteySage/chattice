# Reliability

The reliability contract is built on three verified facts and one
explicit division of labor: Google's documented Chat API quotas,
the gapic SDK's built-in retry behavior, and the framework's no-blind-retry
rule for mutations. The framework does NOT implement its own retry loop;
applications own retry policy. This page documents exactly what the framework
promises, what it deliberately does not, and how to build application-grade
backoff on top of it.

## Retry classification

| Operation | Idempotent? | Framework auto-retry? | Retry strategy |
| --- | --- | --- | --- |
| `messages.get` | Yes — read | No (SDK's internal retries apply) | Safe to retry as an application policy |
| `spaces.get` | Yes — read | No (SDK's internal retries apply) | Safe to retry as an application policy |
| `messages.create` (no `request_id`) | No — creates | **No** | Retry only with a `request_id` (see below) |
| `messages.create` (with `request_id`) | Yes — Google-side | **No** | Retry with the **same** `request_id` |
| `messages.update` | No | **No** | Not auto-retried; application decides |
| `messages.delete` | No | **No** | Not auto-retried; application decides |

The framework never re-issues a transport call on its own. Every `Bot`
operation makes exactly one SDK call per invocation — pinned by tests that
count transport invocations (`tests/reliability/test_timeout_cancellation.py`
asserts a single call even under a forced 429). What the SDK's `grpc_asyncio`
transport does internally (e.g. connect-level retries for transient channel
errors) is outside the framework's control; the framework's own behavior is
the "exactly once per invocation" guarantee.

### request_id: Google-side idempotency for create

`messages.create(..., request_id="...")` maps to the documented `requestId`:
the Chat service deduplicates concurrent or retried creates carrying the same
ID. This is the ONLY safe retry path for message creation:

```python
request_id = f"invite-{space_id}-{attempt}"
try:
    await bot.app.messages.create(space, text, request_id=request_id)
except ChatRateLimitError:
    # retry with the SAME request_id; Google dedupes the duplicate
    await asyncio.sleep(backoff)
    message = await bot.app.messages.create(space, text, request_id=request_id)
```

Without `request_id`, a retried create may deliver the message twice.

## Verified quotas

Quota facts are verified against the Chat API usage limits and documented
here; the framework hardcodes NO quota constants ([capabilities](capabilities.md)
is the only facts table in code, and quotas are not part of it).

| Quota | Value |
| --- | --- |
| Message writes | 3,000 / min per project |
| Per-space rate | **1 write/sec and 15 reads/sec per space** |
| Membership writes | 300 / min |
| Attachment writes | 600 / min |

The per-space 1 write/sec limit is the one that bites interactive bots: a
space that sends one message per second is at the ceiling regardless of the
project-level 3,000/min. Reads are more forgiving (15/sec per space), so
polling and `messages.get`/`spaces.get` loops must still be paced.

## 429 = RESOURCE_EXHAUSTED

A quota-exhausted response arrives as gRPC status `RESOURCE_EXHAUSTED`
("Resource has been exhausted (e.g. check quota)"), which the gapic client
maps to `google.api_core.exceptions.ResourceExhausted` — status 429 at the
HTTP surface. `Bot` wraps it into `ChatRateLimitError` (a `ChatAPIError`
subtype, `chattice.client`); the original SDK error stays reachable via
`.cause`, with `.code` (429) and `.details`.

`Retry-After` is HTTP-semantic, not documented for the Chat API — do not
depend on it. Backoff is an application policy.

## Truncated exponential backoff (application policy)

Google recommends truncated exponential backoff for 429s and transient 5xx.
Chattice adds no retry loop. GAPIC methods retain their SDK retry defaults
unless configured otherwise; an application can add a bounded policy with a
stable request ID:

```python
import asyncio
import random

from chattice.client import Bot, ChatRateLimitError, ChatServiceUnavailableError


async def send_with_backoff(
    bot: Bot, space: str, text: str, *, request_id: str
) -> None:
    for attempt in range(5):
        try:
            await bot.app.messages.create(space, text, request_id=request_id)
            return
        except (ChatRateLimitError, ChatServiceUnavailableError):
            if attempt == 4:
                raise
            await asyncio.sleep(random.uniform(0, min(2**attempt, 32)))
```

This example makes at most five application attempts and adds jitter. SDK
retries may occur within each attempt. Configure a total time budget and
per-call deadlines for the application's requirements.

## Per-call `timeout` semantics

Every `Bot` operation accepts an optional `timeout: float | None` and passes
it to the SDK verbatim as the gRPC call deadline:

- `timeout=None` (default) — no override is passed; the SDK method's own
  default deadline applies.
- `timeout=5.0` — the call must complete within 5 seconds or the SDK raises
  a deadline error, mapped to `ChatServiceUnavailableError`
  (see [bot-api-client](bot-api-client.md)).

The deadline covers the whole RPC (request + response), not connect time
only. Pinned by tests that record the exact timeout on the fake transport
(`tests/reliability/test_timeout_cancellation.py`).

## Cancellation guarantees

`CancelledError` is never swallowed by the framework:

- `Bot` operations contain no `except asyncio.CancelledError` — cancelling
  the task that awaits `messages.create` cancels the underlying SDK call
  immediately; no cleanup block intercepts it.
- The dispatcher does not catch `BaseException`; `CancelledError` propagates
  out of `feed_update` untouched.
- The FastAPI routers (`create_chat_router` etc.) catch `Exception`, not
  `BaseException`, so request cancellation during a handler never collapses
  into a bogus 500 response.

Cancellation is pinned by `tests/reliability/test_timeout_cancellation.py`
(cancel mid-call, assert `CancelledError` surfaces to the caller).

## Idempotency storage + Pub/Sub dedupe (owner-safe state machine)

The push routers use an owner-safe claim/complete/release state machine
(`chattice.idempotency`): `claim(owner, lease)` returns FIRST / COMPLETED
/ ACTIVE; an ACTIVE claim answers **429** so Pub/Sub redelivers later —
incomplete work is never acknowledged. Completed markers are retained
for a bounded window (default 86400 s) so late duplicates are absorbed;
active leases expire atomically (WATCH/MULTI takeover — never two
owners). Keys are namespaced by subscription: Google message IDs are
unique per topic only. Handlers must stay idempotent: push delivery has
no exactly-once guarantee.


## What the framework does NOT do

- No Chattice retry loop; SDK retry policies may make multiple transport
  attempts within an invocation.
- No quota enforcement, pacing, or rate limiting in code.
- No retry budget, circuit breaker, or bulkhead.
- No dedupe without an explicitly configured storage.

These are deliberate: Chat API retry semantics depend on operation identity
(which the framework cannot know) and application constraints (budgets,
deadlines, jitter) that belong at the application edge.

## Concurrency and redelivery rulebook

Google Chat push ingress gives **no ordering guarantee** and can burst
concurrent deliveries (plus Pub/Sub redeliveries). The framework's
correctness must never depend on sequential processing:

1. **Handlers may run concurrently** for the same user/space/thread.
   Shared state must go through the storage contracts (FSM record CAS)
   or application locks — never through handler-local assumptions.
2. **Side effects must be idempotent** or protected by an inbox:
   the push routers dedupe by message id with claim/complete/release
   semantics, but push delivery has NO exactly-once guarantee (Google
   limits exactly-once to pull subscriptions). A redelivered message can
   re-run a handler after a 500.
3. **Interleaved FSM steps conflict loudly, not silently:**
   `compare_and_set` raises `FSMRecordConflict` when the record changed
   between read and write; retry or answer a conflict instead of
   overwriting.
4. **No framework ordering:** handlers observe arrival order only.
   Order-sensitive workflows must record their own sequence numbers.
5. **Cancellation:** the dispatcher does not cancel in-flight handlers on
   shutdown by itself; a lifespan resource can own task supervision (see
   the lifespan contract).
6. **Redis outages fail fast:** idempotency/FSM storages raise; the push
   routers answer 500 so Pub/Sub redelivers. Never degrade to
   "process anyway and hope".


**Memory storage bookkeeping:** the in-memory idempotency/FSM
implementations retain per-key lock objects and completed claims for the
process lifetime — fine for tests and development, unbounded for
long-running servers. Use the Redis implementations in production.
