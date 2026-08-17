# Observability

The framework ships NO telemetry dependency. Observability is a pluggable
application concern reached through a single extension point —
`chattice.observability.ObservabilityHooks` — plus a small set of named
standard-library loggers. This page documents the hook contract, the
failure-isolation guarantee, the no-op default, and how to bridge to OpenTelemetry.

## The ObservabilityHooks contract

`ObservabilityHooks` is a `Protocol` with two async methods, called around
each `feed_update` routing pass (every inbound event, regardless of which
handler wins):

```python
class ObservabilityHooks(Protocol):
    async def before_event(self, event: object, data: dict[str, object]) -> None: ...

    async def after_event(
        self,
        event: object,
        data: dict[str, object],
        result: object,
        error: BaseException | None,
    ) -> None: ...
```

Semantics:

- `before_event` runs before any routing/filter work for the event.
- `after_event` always runs (in a `finally`), even when routing raised; it
  receives the handler `result` (or the error-handler result) and the
  exception via `error`. `error=None` and `result=None` both mean "nothing
  produced" — a handler that returns `None` has no error.
- `data` is the dispatch context: injected dependencies plus the pre-injected
  `state` (FSM) key — the same mapping handlers receive.
- A handler failure is reported through the hook and ALSO routed to the
  error observer; the hook observes, it does not handle.

Configure on the `Dispatcher`:

```python
from chattice import Dispatcher
from myapp.telemetry import OTelHooks

dispatcher = Dispatcher(observability_hooks=OTelHooks())
```

## Failure isolation

A hook exception NEVER affects dispatch. Both hook calls are wrapped:

```python
try:
    await hooks.before_event(event, data)
except Exception:
    _observability_logger.exception("before_event hook failed")
```

The exception is logged to the `chattice.observability` logger (so it is
never silently lost) and dispatch continues. The same guarantee applies to
`after_event` — a broken hook cannot corrupt the `finally` path. This is
pinned by `tests/reliability/test_observability.py`: a hook that raises
still yields a successful dispatch and a fully observed `after_event`.

Loggers used by the framework, all under the `chattice` namespace:

| Logger | Emits |
| --- | --- |
| `chattice.observability` | Hook failures (the failure-isolation path) |
| `chattice.http` | Verification failures, invalid payloads, handler failures, sync-deadline warnings, per-interaction latency |
| `chattice.push` | Pub/Sub and Workspace Events payload/envelope errors, dedupe skips, handler failures |

## The unconfigured default

With `observability_hooks=None` (the default) the dispatcher performs NO
hook calls — there is no hidden no-op object and no overhead per event. The
application opts in by construction; forgetting to configure costs nothing
and breaks nothing.

## OTel bridge example (application-owned)

The following is an EXAMPLE bridge the application writes — it depends on
`opentelemetry-api` / `opentelemetry-sdk`, packages the FRAMEWORK does not
and will not depend on. The framework's only requirement is the three-line
protocol above.

```python
# myapp/telemetry.py — application code, framework-independent
from __future__ import annotations

from typing import Any

from opentelemetry import trace  # external dependency, application-owned
from opentelemetry.trace import Span, Status, StatusCode

from chattice.observability import ObservabilityHooks

_tracer = trace.get_tracer("myapp.chat")


class OTelHooks(ObservabilityHooks):
    def __init__(self) -> None:
        self._spans: dict[int, Span] = {}

    async def before_event(self, event: object, data: dict[str, object]) -> None:
        span = _tracer.start_span(
            f"feed_update {type(event).__name__}",
            attributes={"event.type": type(event).__name__},
        )
        span.set_attribute("event.raw_type", getattr(event, "event_type", "unknown"))
        self._spans[id(event)] = span

    async def after_event(
        self,
        event: object,
        data: dict[str, object],
        result: object,
        error: BaseException | None,
    ) -> None:
        span = self._spans.pop(id(event))
        span.set_status(
            Status(StatusCode.ERROR, repr(error)) if error else Status(StatusCode.OK)
        )
        if result is not None:
            span.set_attribute("handler.result_type", type(result).__name__)
        span.end()
```

Notes for the bridge author:

- The hooks are `async` but the tracer calls are synchronous — keep bridge
  methods small; a slow bridge delays dispatch (the failure-isolation
  guarantee covers exceptions, not latency).
- `event`, `data`, `result` are plain objects; hook code must not mutate
  `data` (dispatch shares the mapping with handlers).
- Exporters, sampling, and resource attributes are application concerns;
  the bridge above only creates spans.
- Trace propagation across the HTTP boundary (extracting `traceparent`
  from the inbound request) belongs in the FastAPI integration layer or a
  Starlette middleware — see [http-transport](http-transport.md) and
  [authentication](authentication.md) for where the framework ends and the
  application begins.
