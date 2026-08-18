# Authentication

There are three different security questions. Do not collapse them:

1. **Did this inbound HTTP request come from Google Chat?** Use
   `GoogleTokenVerifier` with the configured audience.
2. **Which identity calls the outbound Chat API?** Use app credentials for the
   Chat app itself or user credentials for an action on a user's behalf.
3. **Is that identity authorized for this operation and resource?** Scopes,
   Space membership, roles, and administrator approval determine the answer.

## App authentication

Most bots start with a service account and the `chat.bot` scope. The app must
be a member of the target Space.

```python
from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot

provider = ServiceAccountCredentialsProvider.from_service_account_file(
    "/run/secrets/chat-service-account.json"
)
bot = Bot(credentials_provider=provider)
```

`ServiceAccountCredentialsProvider` reads the file lazily. Store the key in a
secret manager or mounted secret, not in the repository. Google's current
service-account procedure is documented in
[Authenticate as a Chat app](https://developers.google.com/workspace/chat/authenticate-authorize-chat-app).

`chat.app.*` scopes are different from `chat.bot`: they require one-time
administrator approval. Declaring a scope locally does not prove that approval
was granted.

## User authentication

Use user OAuth when the operation must happen as a user or access user data.
The application owns consent, callback handling, and durable token storage;
Chattice accepts already-authorized credentials:

```python
from chattice.auth import AuthMode, UserCredentialsProvider
from chattice.client import Bot

provider = UserCredentialsProvider(authorized_user_info)
bot = Bot(credentials_provider=provider, auth_mode=AuthMode.USER)
```

Choose the narrowest scopes required by the methods you call. See Google's
[authentication and authorization matrix](https://developers.google.com/workspace/chat/authenticate-authorize).

### One Bot, both identities

Some Google operations are user-only (`media.upload`), some app-only
(`spaces.messages.attachments.get`), some accept both. Instead of
maintaining two Bots, configure ONE Bot with both identity sources — it
selects the identity per operation based on the capability:

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

Ordinary sends and cards use the app identity; `attachments=[...]`
sends use the user identity **end to end** — `media.upload` AND the
final `messages.create` run on the USER client (the sender of an
attachment message is the authenticated user). Handler code does not
change. See [Files, Images & Media](../guides/files-media.md).

`DelegatedUserCredentialsProvider` uses Domain-Wide Delegation: the
service account impersonates a configured Workspace user via
`with_subject`, and Google treats those calls as user authentication —
one service-account JSON serves both identities. This requires the
Workspace administrator to configure the delegation and scopes. With
real end-user OAuth tokens, pass a `UserCredentialsProvider` instead.

A user-authenticated call acts on behalf of that user; the framework
automates the credential switch but never hides this attribution
semantic.

## Bind a Bot once

```python
from chattice import Dispatcher

dispatcher = Dispatcher(bot=bot)
```

Handlers can then use contextual `message.reply()`, `thread.send()`, and
`space.send()` without fetching those resources. The same `Bot` remains
available for imperative `Bot.send_message()` calls.

Next: [First deployment](first-deployment.md).
