# Capabilities

`chattice.capabilities` answers three DIFFERENT questions with three
capability sets (split after an independent pre-beta review — the pre-split matrix mixed
them):

- `ResponseCapabilities` — what the ingress response channel can do,
  derived from the transport plus the concrete interaction event
  (dialogs, App Home, matched URL, bot/human sender, widget
  autocomplete).
- `OutboundCapabilities` — what an authenticated outbound `Bot` can
  call, derived from the credential kind (app/user) and any reliably known
  credential scopes.
- `PreviewCapabilities` — which Developer Preview features the application
  explicitly enrolled in, expressed with `PreviewFeature` stability flags;
  this is not an auth capability.

Verified Google facts are sourced from the official Chat API
references (see [Google API mapping](../reference/google-api-mapping.md)).

## Response channel (ingress)

`ResponseCapabilities.resolve(transport="http", event=event)`:

| Capability | HTTP | Pub/Sub | Google fact (verified) |
| --- | --- | --- | --- |
| SYNC_RESPONSE | yes | no | 30-second synchronous interaction response; HTTP-only |
| DIALOGS | only command / `REQUEST_DIALOG` action events | no | dialogs only in response to interactions, visible only to the opener |
| CARD_UPDATE_BOT | CARD_CLICKED with BOT sender | no | `UPDATE_MESSAGE` is bot-only |
| CARD_UPDATE_USER | CARD_CLICKED with HUMAN sender, or MESSAGE with a matched URL | no | `UPDATE_USER_MESSAGE_CARDS` for human-sent cards |
| APP_HOME | APP_HOME / SUBMIT_FORM events | no | RenderActions pushCard + separately configured App Home URL |
| UPDATE_WIDGET | WIDGET_UPDATED (autocomplete) | no | autocomplete responses |

`DIALOGS` is derived with one shared predicate (`can_open_dialog`):
commands always may open dialogs; actions only when Google delivered
them with `REQUEST_DIALOG` metadata; SUBMIT/CANCEL actions cannot
return a new dialog. The HTTP serializer guards with the SAME
predicate, so the advertised capability never produces a server error
.

Pub/Sub push and streaming-pull delivery have no synchronous response channel
— both inject an empty `ResponseCapabilities` value and `require()` fails fast
on any response attempt. Apps that must react asynchronously feed a `Bot`
explicitly. HTTP always injects the event-derived value. Thus every supported
ingress supplies the same typed DI key, even when its set is empty.

## Outbound operations (Bot)

`OutboundCapabilities.resolve(auth_mode, scopes=...)` is a **local preflight**,
not an authorization guarantee. The original `resolve(auth_mode)` call remains
valid and treats scope information as unknown.

| Capability | APP scope (any of) | USER scope (any of) | Google fact (verified) |
| --- | --- | --- | --- |
| MESSAGE_CREATE | `chat.bot` | `chat.messages.create`, `chat.messages`, `chat.import` | Chat API `spaces.messages.create` |
| MESSAGE_UPDATE | `chat.bot` | `chat.messages`, `chat.import` | Chat API `spaces.messages.update` |
| ATTACHMENT_UPLOAD | — (not supported) | `chat.messages.create`, `chat.messages`, `chat.import` | Chat API `media.upload` (user auth only) |
| MEDIA_DOWNLOAD | `chat.bot` | `chat.messages.readonly`, `chat.messages` | Chat API `media.download` |
| ATTACHMENT_METADATA_GET | `chat.bot` | — (not supported) | Chat API `spaces.messages.attachments.get` (app auth only) |
| USER_IMPERSONATION | identity-derived, no | identity-derived, yes | OAuth user identity or domain-wide delegation; not a method scope |

When scopes are reliably known, a capability is present when **any** scope in
the identity-specific operation rule is present. For example, the broader
`chat.messages` user scope supports message creation even when the narrower
`chat.messages.create` scope is absent. A known empty or nonmatching set fails
closed before transport. When scopes are unknown, the auth-mode baseline is
preserved so Chattice does not invent a denial or perform a discovery call.

`Bot` reads scopes locally when credentials are lazily resolved. For user
credentials, available `granted_scopes` takes precedence over the credential's
requested/configured `scopes`; for app credentials, configured explicit/default
scopes are considered. This inspection performs no token-info, Google API, or
other network request.

Configured `chat.app.*` scopes do not prove one-time administrator approval.
Likewise, space membership, resource roles, and resource state remain known
only to Google Chat. A call that passes local preflight can therefore still
receive a server-side 403, surfaced as `ChatPermissionDeniedError`.

Beyond the capability set, `Bot` enforces deterministic surface rules
pre-transport (F01): `private_to` requires APP auth and rejects
accessory-widget combinations, `notify` is strict-validated and
APP-gated, and user-auth CARDS are rejected without the documented
preview path (`PreviewFeature.USER_AUTH_CARDS`; the escape hatch is
`Bot.raw_client`).

## require() guards

Both capability sets expose `require(capability)` raising
`CapabilityNotSupported` (a `RuntimeError`):

```python
from chattice.capabilities import (
    CapabilityNotSupported,
    OutboundCapabilities,
    OutboundCapability,
)

capabilities = OutboundCapabilities.resolve(
    auth_mode,
    scopes={"https://www.googleapis.com/auth/chat.messages"},
)
try:
    capabilities.require(OutboundCapability.USER_IMPERSONATION)
except CapabilityNotSupported as error:
    print(error)
```

The message style is operation + actionable hint, so apps can fail with
a useful error instead of a bare permission denial:

```text
USER_IMPERSONATION is not supported in this configuration. Impersonating
users requires user authentication (OAuth or domain-wide delegation).
```

## Pre-transport enforcement contract

Guards run **before Chat API network I/O**. The `Bot` resolves its capability
set from the (explicit or auto-classified) auth mode and locally available
credential scopes, then calls `require()` before issuing the Chat API request.
No separate authorization or token-introspection request is made. This contract
is pinned by tests that count transport invocations: unsupported combinations
never reach the transport (call counter stays zero), supported ones do.

## Developer Preview enrollment

Typed preview routing requires configuration, not merely recognizing a future
wire value. For example, message-action commands are parsed losslessly in all
configurations but reach their dedicated observer only after explicit opt-in:

```python
from chattice import Dispatcher
from chattice.capabilities import PreviewFeature

dispatcher = Dispatcher(preview_features={PreviewFeature.MESSAGE_ACTION})


@dispatcher.message_action()
async def on_message_action(event: CommandEvent) -> None: ...
```

Handlers may inject `PreviewCapabilities` to inspect the immutable enrollment.
A caller cannot bypass configuration by passing a replacement value to
`feed_update()`.

## Experimental namespace

Experimental integrations live in `chattice.experimental`; APIs there may
change or disappear without notice. Preview feature flags remain in the stable
capability model because they gate stable parsing/routing boundaries without
making the preview feature itself stable. Stable core never imports the
experimental namespace; a grep-test enforces that dependency direction.

## Define handlers at module level

Handler functions and their annotations must be defined at module level —
importing dependencies inside a handler (or injecting handler-local
classes into annotations) breaks annotation resolution
(`get_type_hints`) and with it the dependency-injection machinery. This
was verified by the Phase 8 DI tests: local imports resolve to `None`
types, module-level ones resolve correctly.
