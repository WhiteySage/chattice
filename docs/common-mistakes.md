# Common mistakes

## Treating Space as a Telegram chat

Use Google resource names and decide whether you mean the Space top level or a
Thread. Do not build a `chat_id` abstraction over both.

## Confusing a handler return with a Bot call

`return "pong"` answers the current HTTP interaction. `message.reply()` and
`Bot.send_message()` make authenticated Chat API calls. The former cannot be
used after the interaction deadline; the latter needs credentials and can
fail authorization.

## Parsing native commands as message text

Configure commands in the Chat API and route `CommandEvent.command_id` through
`slash_command`, `quick_command`, or Preview-gated `message_action` observers.

## Treating a card action as CallbackQuery

Route Google's named action function and typed `ActionData`; authorize the
actor and re-fetch domain state before a write. Action parameters are not a
trusted authorization token.

## Parsing `formInputs` by hand

Use normalized `FormInputs` or an opt-in `FormModel`. Keep `.raw` only for an
unsupported field.

## Mixing interactions with Workspace Events

Interactions go to `Router` / `Dispatcher`; resource-change CloudEvents go to
`EventsRouter` / `EventsDispatcher`. Their transports, response channels, and
authorization setup differ.

## Assuming local capability means authorized

Capability preflight only proves known local facts. Google still decides
scope grants, membership, role, administrator approval, and Preview
eligibility. Unknown scopes are not an empty scope set.

## Using MockVerifier in production

`MockVerifier` deliberately accepts unauthenticated requests. Use
`GoogleTokenVerifier` for Chat HTTP interactions and an appropriate Pub/Sub
verifier for push endpoints.

## Making business workflows core concepts

Polls, approvals, incidents, tickets, and AI assistants are recipes composed
from cards, actions, forms, state, Threads, and application services.

## Treating experimental or raw APIs as stable facade

Isolate `chattice.experimental`, `Bot.raw_client`, `.raw`, and `RawWidget`
usage. Test and version the exact external schema you depend on.
