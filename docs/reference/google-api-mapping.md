# Google API mapping

Chattice wraps platform primitives and technical boilerplate. The typed facade
never prevents access to the official client or raw payload.

| Chattice concept | Google concept / method | Auth/capability notes | Escape hatch |
| --- | --- | --- | --- |
| `MessageEvent` | interaction `Event.message` | inbound request verification | `event.raw` |
| `SpaceRef` | `Space` resource | resource name `spaces/*` | `event.raw` / `bot.raw.app()` |
| `ThreadRef` | `Thread` nested in Message | resource name or `threadKey` | `event.raw` |
| handler `return str/Card` | synchronous interaction response | HTTP, deadline-limited | return mapping / `RawInteractionResponse` |
| `messages.create` | `spaces.messages.create` | app `chat.bot`; user any supported create scope | `bot.raw.app().create_message` |
| `messages.create(attachments=...)` | `media.upload` → `spaces.messages.create` | USER only for the WHOLE send: upload AND create (sender = HUMAN) | `bot.raw.app()` (create), REST media extra |
| `attachments.upload` | `media.upload` | USER only (`chat.messages.create`/`chat.messages`/`chat.import`) | `chattice[media]` REST client |
| `attachments.download` | `media.download` | app `chat.bot`; user `chat.messages.readonly`/`chat.messages` | REST media extra |
| `attachments.get_metadata` | `spaces.messages.attachments.get` | APP only (`chat.bot`) | `bot.raw.app().get_attachment` |
| `memberships.create` | `spaces.members.create` | APP only; `chat.app.memberships` + administrator approval | `bot.raw.app().create_membership` |
| `memberships.get` | `spaces.members.get` | APP; `chat.bot` or `chat.app.memberships` | `bot.raw.app().get_membership` |
| `memberships.list` | `spaces.members.list` | APP; `chat.bot` or `chat.app.memberships`; explicit `Pager` | `bot.raw.app().list_memberships` |
| `memberships.delete` | `spaces.members.delete` | APP only; `chat.app.memberships` + administrator approval | `bot.raw.app().delete_membership` |
| `spaces.list` | `spaces.list` | APP only (`chat.bot`); caller-member Spaces | `bot.raw.app().list_spaces` |
| `MessageEvent.attachment_refs` | `message.attachment[]` (`attachmentDataRef`/`driveDataRef` oneof) | inbound metadata | `event.attachments` (lossless) |
| `chattice.cards.Image` | Cards v2 `Image` widget | HTTPS URL only | `RawWidget` |
| `F.text.regexp(...)` | — (Python `re`, match-from-start) | n/a | custom `Filter` |
| `messages.update` | `spaces.messages.update` | sender/identity/scope constraints | `bot.raw.app().update_message` |
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
