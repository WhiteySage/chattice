# ADR-008: Separate synchronous and asynchronous response APIs

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

A synchronous interaction response is returned to Google's callback request,
must complete within 30 seconds, targets the originating space, and requires no
Chat API authentication. An asynchronous message is a separate authenticated
Chat API operation with its own retry, idempotency, thread, and authorization
rules. Pub/Sub interaction delivery cannot support every synchronous card or
dialog behavior.

## Decision

`InteractionContext.respond(...)` uses the current `ResponseChannel` and is
available only when that transport supports the requested response. Outbound
resource methods such as `Bot.send_message(...)` always use the Chat API and an
explicit credential context. The framework does not overload one `answer()`
method to choose between them implicitly.

The framework tracks whether a response channel has been consumed and raises a
clear error for unsupported or duplicate terminal responses. Crossing the
30-second deadline does not automatically cancel arbitrary handler work;
integrations surface timing and application authors choose deferral.

## Consequences

Auth, latency, visibility, retry, and thread semantics remain predictable.
Applications must learn two explicit APIs. Convenience helpers may wrap a known
mode but cannot silently fall back from one to the other.

## Alternatives considered

- `message.answer()` selects a mode automatically: concise but ambiguous and
  prone to accidental duplicate or differently attributed messages.
- Always call the Chat API: cannot implement dialogs and wastes synchronous
  response capabilities.
- Always return from the webhook: unsuitable for work beyond the deadline and
  unavailable for asynchronous transports.

## Sources

[receive and respond to interactions](https://developers.google.com/workspace/chat/receive-respond-interactions),
[create a message](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create),
[dialogs](https://developers.google.com/workspace/chat/dialogs),
[Pub/Sub card limitations](https://developers.google.com/workspace/chat/troubleshoot-cards).

