# HTTP transport, verification, synchronous responses

The HTTP transport provides an inbound Google Chat path:

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
header with `google-auth`. HTTPS endpoint audiences use
`verify_oauth2_token`, Google OAuth2 certificates, and a verified Chat-service
email. Project-number audiences use `verify_token` against the Chat
service-account certificate endpoint with explicit issuer checks. One
`audience` string selects the strategy.

All verification failures — including a missing or malformed Authorization
header — produce HTTP 401, as documented by Google. `MockVerifier` exists for
tests and local development only.

## Synchronous response

The sync response deadline is 30 seconds (documented). Handlers either return
a payload (`str` -> `{"text": ...}`, `dict` -> passthrough, `None` -> empty
200) or call `response.respond(payload)`; a second respond raises
`DoubleResponseError`. `REMOVED_FROM_SPACE` must return `None` for an empty
200; attempting to return a message is rejected with a 500. Deadline misses are logged as
warnings; asynchronous replies use the Chat API client.

## Error mapping

| Case | HTTP |
| --- | --- |
| Verification failure | 401 |
| Malformed JSON / invalid payload | 400 `{"error": "invalid_interaction_payload"}` |
| Unhandled handler error / double response / serialization error | 500 |

Logs never include the Authorization header or tokens.
