# Dependency injection

Status: **Implemented**.

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
5. Otherwise `DependencyResolutionError` is raised. The error names the
   handler, parameter, and event type so a failure that happens before the
   callback body runs is still actionable.

```python
@router.message()
async def handler(message: MessageEvent, database, label="default"):
    return database, label


result = await dispatcher.feed_update(event, database=db)
```

Event aliases are conventional unannotated names: `event`, `message`,
`action`, `command`, `added_to_space`, `removed_from_space`, `widget`,
`app_home`, `form`, `dialog_submit`, `dialog_cancel`, `unknown`, `error`, and
`error_event`. A typed event parameter is resolved by its annotation, so the
parameter name can be arbitrary:

```python
@router.slash_command(F.command_id == 1)
async def start(command: CommandEvent, bot: Bot) -> None:
    await bot.app.messages.create(command.space.name, text="Started")
```

`bot` in this example must be supplied by the dispatcher or transport context.
Arbitrary names are not aliases and do not magically receive the event:

```python
@router.message()
async def mistaken(name):
    return name
```

Unless middleware or the dispatcher supplies `name=...`, this raises
`DependencyResolutionError`. Use `message: MessageEvent` (or another typed
event parameter) when the handler needs the event itself.

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
