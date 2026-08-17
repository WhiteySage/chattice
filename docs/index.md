# Chattice

Chattice is an async, typed framework for Google Chat apps. It combines
routers, filters, middleware, dependency injection, and state management with
Google-native concepts: Spaces, Threads, Messages, commands, cards, dialogs,
App Home, and Workspace Events.

## Start here

1. [Install Chattice](getting-started/installation.md).
2. Complete the [5-minute Quickstart](getting-started/quickstart.md).
3. [Configure the Google Chat app](getting-started/google-chat-setup.md).
4. Learn the [Space → Thread → Message mental model](concepts/mental-model.md).
5. Follow the task guides for [messages](guides/messages.md),
   [commands](guides/commands.md), [cards/forms/dialogs](guides/cards-forms-dialogs.md),
   and [Workspace Events](guides/workspace-events.md).

The complete framework-side learning path is executable as
`examples/docs/from_zero.py`. CI runs it without Google credentials, and the
the from-zero journey is exercised in CI on a clean wheel outside the
source tree.

## Stability at a glance

Chattice is in public beta. **The documented stable beta API is frozen:**
existing stable names, signatures, and semantics will not be renamed, removed,
or changed incompatibly during the beta. Additive changes are possible before
1.0.

Three surfaces have different promises:

| Surface | Promise |
| --- | --- |
| Stable beta | Symbols exported by stable packages and documented public members are frozen for the beta. |
| Experimental | `chattice.experimental` can change or disappear before 1.0. |
| Raw / advanced | `Bot.raw_client` and event `.raw` are supported escape hatches whose breadth and evolution follow Google's SDK and wire schema. |

Read the full [stability contract](stability.md) before adopting experimental
or raw features.

## Google-native, aiogram-inspired

Chattice borrows productive Python ergonomics from aiogram; it does not emulate
Telegram. A Google Chat Space is not a Telegram chat, a card action is not a
`CallbackQuery`, and an interaction event is not an `Update`. See
[If you know aiogram](aiogram-comparison.md).

## Pick the right path

- Respond to a user interaction in under 30 seconds: return text, a `Card`, a
  `Dialog`, or an `ActionStatus` from an HTTP handler.
- Continue the known conversation through the Chat API: use
  `message.reply()`, `message.thread.send()`, or `message.space.send()` with a
  `Bot` bound to the `Dispatcher`.
- Send imperatively to any known Space: use `Bot.send_message()`.
- Observe a resource changing independently of an interaction: use the separate
  `EventsRouter` / `EventsDispatcher` path.

Next: [Installation](getting-started/installation.md).
