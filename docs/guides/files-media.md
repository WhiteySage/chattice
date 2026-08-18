# Files, Images, and Media

Google Chat has two different media surfaces. Chattice keeps them apart
instead of pretending they are one feature:

| Surface | What it is | Google primitive | Auth |
|---|---|---|---|
| **Card Image** | A picture rendered inside a card | Cards v2 `Image` | any card-sending auth |
| **Message attachment** | A file uploaded to Chat and attached to a message | `media.upload` → `attachmentDataRef` → `messages.create` | **USER auth** for the upload |

A local PNG/PDF/whatever is an **attachment**, never a Card Image. Card
Images are URL-only (HTTPS). There is no `data:` URL, `file://` path, or
hidden local hosting.

## Send a local file

```python
import os

import imgkit

from chattice.media import InputFile

path = f"{os.path.abspath(os.getcwd())}/static/out3.png"
imgkit.from_string(body, path, options={"xvfb": ""})

await message.reply(attachments=[InputFile.from_path(path)])
```

Chattice uploads the file through Google's media API, receives the
`attachmentDataRef`, and creates the message with the attachment — the
application never touches `MediaFileUpload`, `attachmentDataRef`, or any
upload boilerplate.

Bytes work the same way:

```python
await bot.send_message(
    "spaces/AAA",
    attachments=[
        InputFile.from_bytes(
            png_bytes,
            filename="result.png",
            content_type="image/png",
        )
    ],
)
```

Multiple files are preflighted together (paths, sizes, filenames, auth,
space consistency) before the first upload, then uploaded sequentially
in the order you passed them.

!!! warning "Media upload requires USER authentication"
    `media.upload` accepts **user authentication only**. A
    service-account / app-auth Bot **cannot upload a local file** — this
    is a Google restriction, not a Chattice one, and Chattice fails
    locally with an actionable error instead of a confusing network
    failure. For an app-auth UI picture use a hosted HTTPS Card Image
    instead.

### One Bot, two identities

Google forces two identity classes on a Chat app: app auth (`chat.bot`,
ordinary messages and cards) and user auth (`media.upload` and other
user-scoped operations). Chattice keeps ONE Bot that holds both:

```python
from chattice.auth import (
    DelegatedUserCredentialsProvider,
    ServiceAccountCredentialsProvider,
)
from chattice.client import Bot

bot = Bot(
    app_credentials_provider=ServiceAccountCredentialsProvider.from_service_account_file(
        "/run/secrets/chat-service-account.json"
    ),
    user_credentials_provider=DelegatedUserCredentialsProvider.from_service_account_file(
        "/run/secrets/chat-service-account.json",
        subject="chat-bot-user@company.com",
    ),
)
```

The Bot picks the identity per operation: ordinary sends use the app
identity, `attachments=[InputFile(...)]` uses the user identity. Handler
code stays the same:

```python
await message.reply("Ordinary message")  # APP identity

await message.reply(  # USER identity upload
    attachments=[InputFile.from_path("photo.png")]  # then create
)
```

`DelegatedUserCredentialsProvider` uses Google Workspace Domain-Wide
Delegation: the service account impersonates a configured user
(`with_subject`), and Google treats those calls as user authentication.
This requires the Workspace administrator to configure the delegation
and OAuth scopes. If your application instead has real end-user OAuth
tokens, pass a `UserCredentialsProvider` — acquisition, consent and
token storage stay the application's concern either way.

!!! warning "User-auth calls act on behalf of a user"
    A message created through a user-authenticated call is attributable
    to that user. Chattice automates the credential switch but never
    hides this semantic.

## Show a hosted image in a Card

```python
from chattice.cards import Card, Image, Section

card = Card(
    sections=[
        Section(
            widgets=[
                Image(
                    image_url="https://example.com/result.png",
                    alt_text="Result",
                )
            ]
        )
    ]
)
await message.reply(card=card)
```

`Image` accepts absolute HTTPS URLs only — local paths, bytes and
`data:` URLs are rejected at construction. `on_click` reuses the
existing `Action` / `OpenLink` facades.

## Receive and inspect attachments

Inbound attachments stay lossless (`message.attachments` is untouched)
and gain a typed view:

```python
from chattice.client import Bot


@router.message()
async def on_file(message: MessageEvent, bot: Bot) -> str:
    for attachment in message.attachment_refs:
        if attachment.is_uploaded:
            content = await bot.download_attachment(attachment)
            # or: await bot.download_attachment(attachment, destination="out.bin")
            return f"Got {attachment.filename} ({attachment.mime_type}), {len(content)} bytes"
        if attachment.is_drive:
            return f"Drive file {attachment.drive_file_id} — use the Drive API"
    return "No attachments"
```

`attachment_refs` distinguishes `UPLOADED_CONTENT` from `DRIVE_FILE`.
`thumbnail_uri` / `download_uri` are human-facing links; programmatic
downloads use `attachment_data_ref.resourceName` via
`Bot.download_attachment`.

The symmetric metadata flow:

```python
uploaded = await bot.upload_attachment(space, InputFile.from_path("x.pdf"))
metadata = await bot.get_attachment("spaces/.../messages/.../attachments/...")
content = await bot.download_attachment(metadata)  # or metadata.resource_name
```

`get_attachment` requires app auth + `chat.bot`
(`spaces.messages.attachments.get` is APP-only); download works with
USER or APP scopes; upload is USER-only.

## What is rejected locally

Before any network call, Chattice validates the whole attachment set:

- app auth + `InputFile` → local error (see the warning above)
- `private_to` + attachments → local error (Google: private messages omit attachments)
- `accessory_widgets` + attachments → local error (Google restriction)
- missing path / directory / FIFO / device instead of a regular file
- file larger than 200 MB (Google's upload ceiling)
- empty filename, filename with `/` or `\`, filename without an extension
- an `UploadedAttachment` from Space A sent into Space B

Zero-byte files are **allowed** (Google documents a maximum but no
minimum). File-type restrictions are NOT duplicated locally: Google's
blocked-file-type list is authoritative and may change.

## Optional dependency

Uploads and downloads use the official Google API Client Library media
endpoints (the GAPIC client cannot carry a binary media body), shipped
as an optional extra:

```console
pip install "chattice[media]"
```

Without the extra, media operations raise an actionable error with the
install command. `chattice.media` itself imports without the extra.

See also: [Messages & Threads](messages.md) (private-message rules),
[Authentication](auth-capabilities.md) (the three auth capabilities),
[Cards, Forms & Dialogs](cards-forms-dialogs.md) (typed `Image`).
