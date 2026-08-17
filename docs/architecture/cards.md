# Cards

Phase 5 provides typed facade builders over the official google-apps-card
SDK — no manual Cards JSON.

## Facades

```python
card = Card(
    header=CardHeader(title="Deploy production?"),
    sections=[
        Section(
            widgets=[
                TextParagraph("Deploy v2.1?"),
                ButtonList(
                    buttons=[
                        Button(
                            "Deploy",
                            action="deploy.confirm",
                            parameters={"env": "prod"},
                        ),
                        Button("Cancel", action="deploy.cancel"),
                    ]
                ),
            ]
        )
    ],
)
```

Each facade builds the SDK proto via `to_proto()`, serializes via
`to_dict()` (documented camelCase Cards v2 JSON), and rebuilds via
`from_dict()`/`from_proto()`. `Card.from_dict()` takes a lossless raw JSON
snapshot: unknown top-level/known-widget fields survive `to_dict()`, and
unsupported widgets become `RawWidget` facade entries instead of raising or
being dropped. The raw `.proto` object remains the escape hatch for future
Google SDK fields; schema-unknown JSON cannot be retained by protobuf itself,
so use the JSON path when exact unknown-field round-trip matters.

## Buttons and actions

`Button(action=..., parameters=...)` produces `onClick.action` with string
parameters — the same shape Phase 2 normalizes into `ActionEvent`, so clicks
route through `@router.action("deploy.confirm")`.

A button can also open a dialog: `Button(..., interaction=ButtonInteraction.OPEN_DIALOG)`
serializes `onClick.action.interaction: "OPEN_DIALOG"` — see
[Dialogs & App Home](dialogs-app-home.md).

## Forms and validation

Form widgets carry the full documented field set:

```python
from chattice.cards import (
    DateTimePicker,
    SelectionInput,
    TextInput,
    TextInputType,
    Validation,
)

text = TextInput(
    name="email",
    label="Email",
    hint_text="you@example.com",
    value="",
    validation=Validation(character_limit=254, input_type=TextInputType.EMAIL),
)
select = SelectionInput(
    name="tier",
    label="Tier",
    items=[{"value": "free", "text": "Free"}, {"value": "pro", "text": "Pro"}],
)
picker = DateTimePicker(name="deadline", label="Deadline")
```

- `TextInput` — `name`, `label`, optional `hint_text`, `value`, and
  `validation` (Phase 6).
- `SelectionInput` — `name`, `label`, and `items` (value/text pairs).
- `DateTimePicker` — `name`, `label`, optional `value_ms_epoch` and
  `timezone_offset_date`.

`Validation` enforces rules client-side per the documented JSON:
`characterLimit` (max input length) and `inputType` (`TEXT`, `INTEGER`,
`FLOAT`, `EMAIL`, `EMOJI_PICKER`).

Submitted widget values arrive back in `event.form_inputs` as typed
`FormInputs` values (`StringInput`, `DateInput`, `DateTimeInput`, `TimeInput`)
via the Phase 2 parser, and `Section.from_proto()` rebuilds form widgets from
a raw SDK proto — closing the Phase 5 round-trip gap for form widgets.

## Sync card updates

A handler returning a `Card`:
- for MESSAGE events → `{"cardsV2": [...]}`;
- for CARD_CLICKED → `{"actionResponse": {"type": "UPDATE_MESSAGE"}, "cardsV2": [...]}`.

`UPDATE_MESSAGE` is documented as «only permitted on a CARD_CLICKED event
where the message sender type is BOT». Updating cards on human messages
uses `UPDATE_USER_MESSAGE_CARDS` (implemented, Phase 14 — sender-derived:
BOT → UPDATE_MESSAGE, HUMAN → UPDATE_USER_MESSAGE_CARDS; a MESSAGE with
a matched URL also updates via UPDATE_USER_MESSAGE_CARDS). Async card
updates go through `bot.update_message`.
