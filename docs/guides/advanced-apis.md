# Advanced Google Chat APIs

Chattice follows a curated-facade rule (ADR-012): a method enters the stable
high-level API only when Chattice adds real value over the generated SDK —
identity routing, capability preflight, semantic validation, pagination,
error normalization, cards/types integration, or a meaningful helper.
Transparent 1:1 passthrough and niche surface stay on the raw tier, which is
a first-class home, not an apology:

```python
from chattice.client import Bot


async def get_space_raw(bot: Bot) -> object:
    app_client = await bot.raw.app()
    return await app_client.get_space(name="spaces/AAA")


# Or, for operations that need the USER identity:
user_client = await bot.raw.user()
```

`bot.raw.app()` / `bot.raw.user()` are async because credential resolution is
lazy. Method availability, request protos, fields, and behavior follow
`google-apps-chat` and the live Google Chat API rather than the Chattice
stable facade.

## Operation families

| Family | Chattice high-level status | Identity/status note |
| --- | --- | --- |
| Message create/get/update/delete | stable `bot.app.messages` / `bot.user.messages` | explicit identity; app/user support varies by scope |
| Space get | stable `bot.app.spaces.get` | app must normally have access/membership |
| Space list | stable `bot.app.spaces.list` | APP + `chat.bot`; caller-member Spaces, not organization-wide search |
| Space create/search/update/delete | raw official client | app, user, admin, or importer rules differ by method |
| Human user memberships | stable `bot.app.memberships` (create/get/list/delete) | APP only; create/delete require admin-approved `chat.app.memberships` |
| Group, external-user, or Chat-app memberships | raw official client where Google supports the case | auth and role constraints vary |
| Message get/list/delete | curated `bot.app.messages` / `bot.user.messages` | explicit identity; list returns a `Pager` |
| Message search | raw official client | user/admin/app results and scopes differ |
| Reactions | curated `bot.user.reactions` (create/list/delete) | USER only; reaction-specific scopes |
| Attachments | curated `bot.app.attachments` / `bot.user.attachments` + lossless `MessageEvent.attachments` | upload is USER-only; metadata get is APP-only; download accepts either |
| Pins | raw/Preview | Google Developer Preview; explicit account eligibility and scopes |
| Read state / thread read state / notification settings | curated `bot.user.users.*` | USER only; `chat.users.readstate*` / `chat.users.spacesettings` |
| Availability, user sections | raw official client | generally user-specific; consult each method's auth table |
| Custom emoji | raw official client | custom-emoji scopes and organizational policy apply |
| Import mode | raw official client | admin/domain-wide setup and `chat.import` semantics apply |

Never infer authorization from method presence in the SDK. Check the current
[Google authentication matrix](https://developers.google.com/workspace/chat/authenticate-authorize),
request the narrowest scope, and expect Google to enforce resource permission
after local preflight.

## Opening a direct chat from a card

Cards render clickable links via the HTML subset (`<a href="...">` in
text widgets), but user mentions (`<users/...>`) exist only in the
message TEXT — they never render inside card widgets. Two supported
ways to point a user at a direct chat:

1. Mention next to the card (the chip opens the direct chat):
   `bot.app.messages.create(space, text="<users/123> See the card", card=card)`.
2. Use the OFFICIAL space URI: a direct-message `Space` returned by
   `find_direct_message` / `get_or_setup_direct_message` carries
   `space_uri` — the URI users can use to access the space. Wrap it in
   a card link or button:

```python
space = await bot.user.spaces.get_or_setup_direct_message("hr@example.com")
card = Card(
    sections=[
        Section(
            widgets=[
                Button(
                    text="Open chat",
                    open_link=space.space_uri,
                ),
                # Or as clickable inline text: card text fields support
                # the HTML subset, including <a href>.
                TextParagraph(
                    text=f'Open the chat: <a href="{space.space_uri}">link</a>'
                ),
            ]
        )
    ]
)
```

`space_uri` is a Google-provided field; no unofficial deep-link formats
are used.

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

## Per-call request configuration

Every curated resource method accepts an optional
`config=RequestConfig(timeout=..., retry=..., metadata=...)`. `timeout=`
remains as a shorthand; `config=` wins when both are given. A default
`RequestConfig` reproduces raw GAPIC defaults exactly (absent values are
omitted from the GAPIC call):

```python
from chattice.client.config import RequestConfig

space = await bot.user.spaces.find_direct_message(
    "hr@example.com",
    config=RequestConfig(timeout=5.0),
)
```

All curated calls flow through ONE execution path:
resource client -> OperationExecutor -> OperationRegistry preflight ->
explicit APP/USER GAPIC client. Google API errors arrive as the curated
`Chat*Error` family; other exceptions pass through untouched.
