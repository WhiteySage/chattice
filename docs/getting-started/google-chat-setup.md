# Create and configure a Google Chat app

These steps describe the Google-hosted side of an HTTP Chattice app. Google
Console labels can evolve; the linked official pages are the source of truth.

## Prerequisites

You need a Google Cloud project and a Workspace account with Google Chat. In
the Cloud project:

1. Enable the **Google Chat API**.
2. Open **Google Chat API → Configuration**.
3. Enter the app name, avatar URL, and description.
4. Enable interactive features. Enable joining Spaces if the app should work
   outside direct messages.
5. Under connection settings, choose **HTTP endpoint URL** and enter the
   public HTTPS URL serving the FastAPI route.
6. Choose the authentication audience: the endpoint URL or Cloud project
   number. Put the same value in `CHATTICE_AUDIENCE`.
7. Under visibility, add the people or Google Groups allowed to install and
   test the app.
8. Save the configuration.

Google's current field descriptions are in
[Receive and respond to interaction events](https://developers.google.com/workspace/chat/receive-respond-interactions).
For a self-hosted endpoint, `GoogleTokenVerifier` validates the bearer token
described in [Verify requests from Google Chat](https://developers.google.com/workspace/chat/verify-requests-from-chat).

## Configure a native slash command

Under **Commands**, add a command:

- Command ID: `42` (IDs are numeric and configured by you).
- Command type: **Slash command**.
- Name: `/deploy`.
- Description: `Deploy an environment`.

Save again. The ID, not the display text, is the durable routing key in
Chattice. The official command guide documents slash commands, quick commands,
and Developer Preview message actions:
[Respond to Google Chat app commands](https://developers.google.com/workspace/chat/commands).

## App Home and dialogs

Dialogs use the same HTTP interaction endpoint and open only in response to an
eligible interaction. App Home is separately enabled/configured in the Chat
app settings but is handled by the same Chattice HTTP router. Neither surface
has a synchronous response channel over Pub/Sub.

## Outbound credentials are separate

The hello handler returns a synchronous interaction response and needs no
outbound credential. `message.reply()`, `thread.send()`, `space.send()`, and
`Bot.send_message()` call the Chat API and therefore need app or user
credentials. Set those up next; never commit a service-account key.

Next: [Authentication](authentication.md).
