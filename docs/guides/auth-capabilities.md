# Authentication and capabilities

Capabilities are local, typed preflight checks. They improve error messages and
prevent deterministic invalid requests; they do not replace Google's
authorization decision.

## Three capability sets

- `ResponseCapabilities`: what this transport and concrete event can return.
- `OutboundCapabilities`: what this credential identity and known scopes can
  attempt through `Bot`.
- `PreviewCapabilities`: which Developer Preview routes the application has
  explicitly enabled.

## Scope-aware outbound preflight

For message creation, app auth accepts `chat.bot`; user auth accepts **any of**
`chat.messages.create`, `chat.messages`, or `chat.import`. For updates, user
auth accepts either `chat.messages` or `chat.import`.

The three media capabilities follow the same tri-state model:

| Capability | App auth | User auth | Admissible scopes |
| --- | --- | --- | --- |
| `ATTACHMENT_UPLOAD` (`media.upload`) | ❌ | ✅ | user: `chat.messages.create` / `chat.messages` / `chat.import` |
| `MEDIA_DOWNLOAD` (`media.download`) | ✅ | ✅ | app: `chat.bot`; user: `chat.messages.readonly` / `chat.messages` |
| `ATTACHMENT_METADATA_GET` (`spaces.messages.attachments.get`) | ✅ | ❌ | app: `chat.bot` |

A dual-identity Bot resolves these against the identity the operation
needs: `Bot.upload_attachment` and `attachments=[InputFile(...)]` use
the USER identity, `Bot.get_attachment` uses the APP identity,
`Bot.download_attachment` accepts either. See
[Files, Images & Media](files-media.md).

`scopes=None` means **unknown**, not empty. Chattice preserves the auth-mode
baseline and lets the server decide; it performs no hidden discovery or token
introspection call. An explicit empty iterable means reliably known absence and
fails locally.

```python
from chattice.auth import AuthMode
from chattice.capabilities import OutboundCapabilities, OutboundCapability

unknown = OutboundCapabilities.resolve(AuthMode.USER, scopes=None)
known = OutboundCapabilities.resolve(
    AuthMode.USER,
    scopes={"https://www.googleapis.com/auth/chat.messages"},
)
known.require(OutboundCapability.MESSAGE_CREATE)
```

Passing preflight is not an authorization guarantee. Google can still return
403 because of missing consent/admin approval, Space membership, resource
role, policy, or resource state. Chattice surfaces this as
`ChatPermissionDeniedError`.

## 401 vs 403 vs capability errors

| Error | Meaning | First check |
| --- | --- | --- |
| Incoming HTTP 401 | request verification failed | exact audience, bearer token, Google identity, clock/network |
| `ChatUnauthenticatedError` | outbound credential was rejected | key/token validity and refresh |
| `CapabilityNotSupported` | configuration is deterministically unsupported | auth mode, known scopes, transport/event, Preview opt-in |
| `ChatPermissionDeniedError` | Google authenticated the call but denied it | scope grant, app membership, role, admin approval, feature enrollment |

## Preview opt-in

```python
from chattice import Dispatcher
from chattice.capabilities import PreviewFeature

dispatcher = Dispatcher(
    preview_features={
        PreviewFeature.MESSAGE_ACTION,
        PreviewFeature.PINNED_MESSAGES,
    }
)
```

Enrollment in Chattice is only an explicit application decision. The Google
account must separately be eligible/enrolled and have the required identity,
scopes, and resource permissions.

Next: [Recipes](../cookbook/recipes.md).
