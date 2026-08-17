# HTTP and Pub/Sub

The same interaction parser and `Dispatcher` sit behind both transports, but
their response capabilities are not interchangeable.

| Behavior | HTTP interactions | Pub/Sub push / streaming pull |
| --- | --- | --- |
| Delivery | HTTPS request | Pub/Sub message |
| Ack | HTTP response | 2xx push ack or subscriber ack |
| Synchronous text/card response | yes, within the interaction deadline | no |
| Dialog and App Home | yes, for eligible events | no |
| Outbound `Bot` calls | yes | yes |
| Return value over push | serialized to Chat | ignored (push) / mapped outbound where supported (pull runner) |

## HTTP

Use `create_chat_router(dispatcher, GoogleTokenVerifier(...))`. Verification is
fail-closed and failures return 401. Handler returns are serialized by event
type, including sender-sensitive card updates and HTTP-only dialogs/App Home.

## Pub/Sub push

Use `create_pubsub_router` with a `GooglePubSubVerifier`. Pub/Sub expects an
ack, not a Chat response, so handler results cannot answer the interaction.
Use an injected `Bot` for a later message or update. Failed deliveries can be
retried; make effects idempotent.

## Pub/Sub streaming pull

Install `chattice[pubsub]`, then run
`dispatcher.run_pubsub(subscription, bot=bot)`. This is a persistent Pub/Sub
subscriber stream with acknowledgements and delivery attempts, not
Telegram-style long polling. Dialog and App Home responses remain unsupported.

Choose HTTP for interactive UI. Choose Pub/Sub when infrastructure policy or
behind-VPN consumption requires it and the application can respond through
authenticated Chat API calls.

Next: [Authentication and capabilities](auth-capabilities.md).
