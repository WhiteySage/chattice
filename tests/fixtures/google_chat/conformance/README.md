# Personal/shared conformance fixture provenance

Retrieved and minimized on **2026-08-16** from current stable Google Chat
interaction schemas. Identifiers, names, function names, and values are
sanitized placeholders; no captured user data is present.

Primary sources:

- [Event REST reference](https://developers.google.com/workspace/chat/api/reference/rest/v1/Event)
- [EventType reference](https://developers.google.com/workspace/chat/api/reference/rest/v1/EventType)
- [Commands guide](https://developers.google.com/workspace/chat/commands)
- [Form-input guide](https://developers.google.com/workspace/chat/read-form-data)
- [Private-message guide](https://developers.google.com/workspace/chat/create-messages#send-a-message-privately)
- [Pub/Sub guide](https://developers.google.com/workspace/chat/quickstart/pub-sub)

| Fixture | Derivation |
| --- | --- |
| `private_command.json` | Stable `APP_COMMAND` / `QUICK_COMMAND` Event shape in a named Space. |
| `private_card_button.json` | Stable `CARD_CLICKED` Event with its bot-authored Message and immutable `privateMessageViewer` output. |
| `private_card_form.json` | Same private Message action plus documented `common.formInputs.stringInputs`. |
| `shared_thread_card_click_alice.json` | `CARD_CLICKED` on a bot Message with an explicit `message.thread.name`. |
| `shared_thread_card_click_bob.json` | Same shared Message/Thread resource, with a different event `user`. |
| `dm_card_click.json` | `CARD_CLICKED` in a `DIRECT_MESSAGE` Space, without a Thread dependency. |
