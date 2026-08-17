# Advanced Google Chat APIs

Chattice's stable high-level `Bot` deliberately covers common message CRUD and
Space lookup. The official async Google client remains available for the rest:

```python
from chattice.client import Bot


async def get_space_raw(bot: Bot) -> object:
    client = bot.raw_client
    return await client.get_space(name="spaces/AAA")
```

`Bot.raw_client` is a supported escape hatch, but method availability, request
protos, fields, and behavior follow `google-apps-chat` and the live Google Chat
API rather than the Chattice stable facade.

## Operation families

| Family | Chattice high-level status | Identity/status note |
| --- | --- | --- |
| Message create/get/update/delete | stable `Bot` facade | app/user support varies by method and scope |
| Space get | stable `Bot.get_space` | app must normally have access/membership |
| Space create/list/search/update/delete | raw official client | app, user, admin, or importer rules differ by method |
| Memberships | raw official client | membership/role and app-vs-user scopes matter |
| Message search/list | raw official client | user/admin/app results and scopes differ |
| Reactions | event summaries + raw official client | use reaction-specific scopes for API calls |
| Attachments | lossless `MessageEvent.attachments` + raw official client | media/download auth is method-specific |
| Pins | raw/Preview | Google Developer Preview; explicit account eligibility and scopes |
| Availability/read state/notifications/user sections | raw official client | generally user-specific; consult each method's auth table |
| Custom emoji | raw official client | custom-emoji scopes and organizational policy apply |
| Import mode | raw official client | admin/domain-wide setup and `chat.import` semantics apply |

Never infer authorization from method presence in the SDK. Check the current
[Google authentication matrix](https://developers.google.com/workspace/chat/authenticate-authorize),
request the narrowest scope, and expect Google to enforce resource permission
after local preflight.

## Incoming webhooks

An incoming webhook is an outbound-only URL for posting into one configured
Space. It cannot receive interactions and does not need Chattice. Use it for a
simple one-way integration; use a full Chat app when you need interactions,
multiple Spaces, app/user identity, cards with actions, dialogs, or Workspace
Events.

## Raw payload discipline

Keep raw calls in a small adapter module, pin the `google-apps-chat` range,
record the required auth/Preview status, and add a fixture or mock-transport
test. When exact unknown field round-trip matters, preserve `event.raw` rather
than assuming the curated event exposes it.
