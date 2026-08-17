# ADR-009: Google interaction envelope and common-data normalization

- Status: Accepted
- Date: 2026-08-13
- Owners: maintainers

## Context

Google's direct Chat interaction `Event` reference uses a top-level `type` and
`common`, while official App Home HTTP samples read the interaction from
`chat` and callback information from outer `commonEventObject`. Form inputs are
typed one-of values, not a string map. Google can add fields and enum strings.

## Decision

Phase 2 accepts both documented envelope families through one pure adapter.
The original complete mapping is deep-copied before normalization. Direct and
wrapped data are compared when both appear; conflicts fail rather than choosing
one silently. Outer `commonEventObject` and direct `common` normalize to a
framework common-data view but remain distinct in raw data.

Permissive Pydantic v2 models validate the untrusted boundary with extra fields
allowed. Frozen/slotted dataclasses remain the public domain. Action parameters
are immutable strings and remain separate from typed `FormInputs`. Unknown
event strings map to `UnknownEvent`; malformed types and `UNSPECIFIED` fail.

Workspace add-on `chat.*Payload` objects and Workspace Events CloudEvents are
different schemas and are not accepted by this adapter.

## Consequences

Handlers receive the same domain vocabulary across documented Chat HTTP
envelopes and never traverse Google dictionaries for ordinary work. Raw data
remains available for forward-compatible escape hatches. Deep copying has a
bounded per-event allocation cost. New envelope families require explicit
support and fixtures rather than accidental permissive merging.

## Alternatives considered

- Treat direct `Event` as the only canonical payload: contradicts official App
  Home samples.
- Flatten all input into strings: loses multiselect, epoch, component-presence,
  and time information.
- Make Pydantic models the domain: couples core routing and handler identity to
  an external validation technology.
- Accept every `chat.*Payload` add-on envelope: conflates Chat API interactions
  with the separately documented Workspace add-on schema.

## Sources

[Event REST reference](https://developers.google.com/workspace/chat/api/reference/rest/v1/Event),
[EventType](https://developers.google.com/workspace/chat/api/reference/rest/v1/EventType),
[form data](https://developers.google.com/workspace/chat/read-form-data),
[App Home](https://developers.google.com/workspace/chat/send-app-home-card-message),
and [dialogs](https://developers.google.com/workspace/chat/dialogs).
