# Dispatcher and router semantics

Status: **Implemented for Phase 1**. See
[ADR-002](../adr/ADR-002-dispatcher-router.md).

## Registration

Every interaction `Router` owns `message`, `action`, `command`,
`slash_command`, `quick_command`, `message_action`, `added_to_space`,
`removed_from_space`, `widget_updated`, `app_home`, `form_submit`,
`unknown_event`, `event`, and `error` observers. Observers support decorators
and programmatic registration:

```python
@router.message(F.text == "ping")
async def ping(message: MessageEvent) -> str:
    return "pong"


router.message.register(other_handler, custom_filter)
```

`router.action("deploy.confirm")` is exactly action-name filter sugar. It does
not imply any Google Cards parsing.

`slash_command` and `quick_command` route stable typed `CommandKind` values.
`message_action` is reachable only when the dispatcher explicitly enables
`PreviewFeature.MESSAGE_ACTION`; raw parsing remains forward-compatible when
it is disabled. Resource-change notifications use the separate
`chattice.workspace_events.EventsRouter` and `EventsDispatcher` runtime.

## Hierarchy and traversal

`include_router()` builds an acyclic single-parent tree. Self-inclusion,
cycles, attaching a dispatcher as a child, and reusing an attached router under
another parent raise `RouterConfigurationError`.

Traversal is pre-order depth-first: the current router, then descendants in
inclusion order. Handler registration order is preserved inside each observer.

## Observer precedence

Routing has two global passes:

1. Visit the matching specific observer (`message`, `action`, or
   `unknown_event`) across the whole tree.
2. Only if no specific handler handles the event, visit generic `event`
   observers across the whole tree.

This ensures a generic handler on an ancestor cannot preempt a specific handler
on a descendant. `ErrorEvent` uses only `error` observers and never falls into
ordinary generic handlers.

## Propagation

Filters and handlers run deterministically in registration order. The first
candidate whose filters match and whose middleware/handler returns normally is
the result, even when that result is `None`.

- Raising `SkipHandler` from a filter, middleware, or handler skips that
  candidate and continues.
- Raising `StopPropagation` stops both specific and generic search and returns
  `None`.
- No match returns `None`.

Both control primitives derive from a dedicated `BaseException` subclass so
ordinary `except Exception` middleware does not accidentally transform normal
routing control. There is no implicit fan-out.

## Errors

An ordinary exception creates an `ErrorEvent(source_event, exception)` and is
offered once to error observers in router traversal order. A normally returning
error handler handles it and its return value becomes the dispatch result. If
no error handler handles it—or error routing is explicitly stopped—the exact
original exception is re-raised. A failure in an error handler propagates with
the original exception as its cause; error routing does not recurse.
