# Dependency injection

Status: **Implemented for Phase 1**.

Dependency injection is signature-based and contains no service container,
provider graph, scopes, or FastAPI dependency model.

## Resolution

For every handler parameter, resolution is deterministic:

1. An annotation compatible with the current `Event` subtype receives the
   event, regardless of parameter name.
2. An unannotated conventional alias (`event`, `message`, `action`, `unknown`,
   `error`, or `error_event`) receives the matching event.
3. Other parameters resolve by name from `feed_update()` context, filter
   mappings, or middleware mutations.
4. An omitted parameter with a Python default uses that default.
5. Otherwise `DependencyResolutionError` is raised.

```python
@router.message()
async def handler(message: MessageEvent, database, label="default"):
    return database, label


result = await dispatcher.feed_update(event, database=db)
```

Filter mappings cannot redefine an existing key, including one from another
filter or the caller. Such collisions raise `ContextConflictError` instead of
depending on merge order. Middleware mutation is explicit imperative behavior
and uses normal mapping assignment.

## Caching and signature limits

Handler signatures and resolved type hints compile into immutable
`HandlerPlan` objects cached by callback. Request-specific event and context
values are resolved anew for every dispatch and are never cached.

Positional-only parameters, `*args`, and `**kwargs` are rejected at
registration. Keyword-only parameters are supported. Handlers must return an
awaitable; a synchronous callback fails with `InvalidHandlerError`.

