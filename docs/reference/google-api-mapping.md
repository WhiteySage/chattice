# Google API mapping

Chattice wraps platform primitives and technical boilerplate. The typed facade
never prevents access to the official client or raw payload.

| Chattice concept | Google concept / method | Auth/capability notes | Escape hatch |
| --- | --- | --- | --- |
| `MessageEvent` | interaction `Event.message` | inbound request verification | `event.raw` |
| `SpaceRef` | `Space` resource | resource name `spaces/*` | `event.raw` / `Bot.raw_client` |
| `ThreadRef` | `Thread` nested in Message | resource name or `threadKey` | `event.raw` |
| handler `return str/Card` | synchronous interaction response | HTTP, deadline-limited | return mapping / `RawInteractionResponse` |
| `Bot.send_message` | `spaces.messages.create` | app `chat.bot`; user any supported create scope | `Bot.raw_client.create_message` |
| `Bot.update_message` | `spaces.messages.update` | sender/identity/scope constraints | `Bot.raw_client.update_message` |
| `Button` / `ActionEvent` | Cards v2 `onClick.action` / `CARD_CLICKED` | parameters are strings | `RawWidget`, `event.raw` |
| `FormInputs` / `FormModel` | `common.formInputs` | surface-specific response | `event.raw` |
| `Dialog` | `actionResponse.type=DIALOG` | eligible HTTP interaction only | raw response mapping |
| `AppHomeEvent` | App Home RenderActions | HTTP-only configured surface | `event.raw` |
| `CommandEvent` | slash `MESSAGE` / `APP_COMMAND` | numeric configured ID; message action Preview | `event.raw` |
| `WorkspaceEvent` | Google Workspace Events CloudEvent | subscription identity/scopes | `event.data`, envelope parser |

Typed Card facades map to Google Cards v2 protos from `google-apps-card`.
`Card.to_proto()`/`to_dict()` and supported `from_proto()` reconstruction make
the boundary visible. `RawWidget` preserves a documented widget shape that is
not yet curated.

The [API reference](../api.md) renders signatures from current source and the
[public API inventory](../public-api.md) defines the stable import surface.

Official REST reference:
[Google Chat API v1](https://developers.google.com/workspace/chat/api/reference/rest).
