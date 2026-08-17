# Google Chat mental model

Learn this model before advanced APIs. Chattice uses Google resource names and
interaction semantics directly; it is not a Telegram vocabulary adapter.

```text
Space
├── top-level Message
└── Thread
    ├── Message
    ├── Message
    └── Card → Action
```

## Space → Thread → Message

A **Space** is the addressing boundary. Direct messages, group conversations,
and named Spaces are all Spaces and use resource names such as `spaces/AAA`.

A **Thread** groups related messages inside a Space. Its name looks like
`spaces/AAA/threads/T1`. A top-level message can start a thread; a reply
continues one. Not every Space presents threading in the same way, so choose
reply behavior explicitly when correctness depends on the thread existing.

A **Message** contains text, cards, annotations, attachments, a sender, and
possibly a Thread. `MessageEvent` is the normalized interaction view;
`MessageRef`, `SpaceRef`, and `ThreadRef` are small immutable references.

## Three ways to send

```python
@router.message()
async def answer(message: MessageEvent) -> str:
    await message.reply("continue the incoming thread")
    assert message.thread is not None
    await message.thread.send("explicitly continue this thread")
    assert message.space is not None
    await message.space.send("new top-level Space message")
    return "current interaction response"
```

- Returning the string answers the current HTTP interaction synchronously.
- The three contextual methods call the authenticated `Bot` bound to the
  `Dispatcher`; they use already-known context and do not fetch resources.
- `Bot.send_message("spaces/AAA", ...)` is the imperative equivalent for code
  that is not handling a message or targets another Space.

Contextual sends and imperative sends are both official. Neither is a hidden
alias for the synchronous handler return.

## Interactions vs resource events

```text
User interaction
      ↓
Router / Dispatcher
      ↓
Message, Command, Action, Dialog, App Home

Google resource changed
      ↓
Google Workspace Events subscription
      ↓
EventsRouter / EventsDispatcher
```

Interactions mean a user invoked the app: sent it a message, selected a
command, clicked a card, submitted a dialog, or opened App Home. They use the
normal `Router` and may have an HTTP synchronous response.

Workspace Events report resource changes such as a message, membership,
reaction, or Space changing. They are CloudEvents delivered through a
subscription and use the deliberately separate `EventsRouter`. They are not
fallback interaction payloads and must not be fed into `Dispatcher.feed_update`.

## Message, Card, Dialog, App Home

- A **Message** is content in a Space, optionally threaded or private.
- A **Card** is structured content attached to a message or rendered on another
  Chat surface. Buttons invoke named Actions.
- A **Dialog** is a modal, card-based interaction visible only to its opener.
  It is opened synchronously from an eligible HTTP interaction.
- **App Home** is the app's private home surface. It renders cards through
  HTTP-only `APP_HOME` / `SUBMIT_FORM` responses and is configured separately
  in the Chat app.

Next: [Messages](../guides/messages.md).
