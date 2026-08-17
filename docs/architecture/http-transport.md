# HTTP transport, verification, synchronous responses

Phase 3 adds the first inbound Google Chat path:

```text
HTTPS POST -> verification -> parsing -> Dispatcher -> handler -> sync response
```

## Boundaries

- `chattice/transports/http/` is the web-framework-neutral core. It has no
  Starlette/FastAPI imports and speaks plain mappings, bytes, and dataclasses.
- `chattice/integrations/fastapi/` is the optional FastAPI integration
  (`chattice[fastapi]`); the endpoint itself works with Starlette
  `Request`/`Response` primitives (registered as a plain Starlette route), so
  the produced router also works under plain Starlette
  (`Starlette(routes=chat_router.routes)`).
- The Dispatcher is unchanged: handlers receive `request`, `response`, and
  `interaction` through the existing name-based DI.

## Verification

`GoogleTokenVerifier` verifies the bearer token from the `Authorization`
header against the documented Chat issuer certificates
(`chat@system.gserviceaccount.com` x509 metadata endpoint) using
`google-auth`, supporting both documented Authentication Audience strategies
(endpoint URL / project number) through a single `audience` string.

All verification failures — including a missing or malformed Authorization
header — produce HTTP 401, as documented by Google. `MockVerifier` exists for
tests and local development only.

## Synchronous response

The sync response deadline is 30 seconds (documented). Handlers either return
a payload (`str` -> `{"text": ...}`, `dict` -> passthrough, `None` -> empty
200) or call `response.respond(payload)`; a second respond raises
`DoubleResponseError`. `REMOVED_FROM_SPACE` receives an empty 200 because a
Message response is not possible there. Deadline misses are logged as
warnings; the documented async reply path (Chat API) arrives in Phase 4.

## Error mapping

| Case | HTTP |
| --- | --- |
| Verification failure | 401 |
| Malformed JSON / invalid payload | 400 `{"error": "invalid_interaction_payload"}` |
| Unhandled handler error / double response / serialization error | 500 |

Logs never include the Authorization header or tokens.
