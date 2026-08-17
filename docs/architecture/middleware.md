# Middleware

Status: **Implemented for Phase 1**.

## Contract

```python
class BaseMiddleware:
    async def __call__(self, handler, event, data):
        return await handler(event, data)
```

Register middleware on a router with either
`router.middleware(middleware)` or `router.middleware.register(middleware)`.
The one Phase 1 layer runs after all candidate filters pass and wraps dependency
resolution plus handler invocation.

## Where middleware sits in the request pipeline

The documented order of the full ingress pipeline (verification is NOT
dispatcher middleware — it happens in the transport layer):

```text
transport verification (GoogleTokenVerifier / GooglePubSubVerifier, 401)
    ->
adapter parse (400 on malformed payloads)
    ->
dispatcher filters (incl. ActionData/FormModel decode filters)
    ->
post-filter middleware (router-scoped, outside-in)
    ->
DI resolution + handler invocation
    ->
response serialization
```

## Ordering and hierarchy

Registration order is outside-in:

```text
middleware A before
middleware B before
handler
middleware B after
middleware A after
```

Parent-router middleware wraps child-router middleware. A candidate receives a
fresh copy of feed context, so mutations from a skipped candidate do not leak
into later candidates.

## Capabilities

Middleware can mutate `data` to inject dependencies, return without calling the
next handler to short-circuit, establish async resource lifetimes, and observe
or transform ordinary exceptions. It can also raise `SkipHandler` or
`StopPropagation` explicitly.

There is no outer/inner split in Phase 1. Filters do not trigger middleware
until they match, which keeps the contract small. A second layer should be
introduced only for a concrete pre-filter requirement.

