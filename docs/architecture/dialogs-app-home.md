# Dialogs & App Home

Phase 6 adds the two interaction-driven UI surfaces that go beyond plain
message cards: **dialogs** (modal forms opened from a button) and the
**App Home** tab (the bot's private space with a home card).

Both are synchronous-response flows: the handler returns a typed facade and
the FastAPI integration serializes it into the documented REST response — no
asynchronous calls, no manual JSON.

## Opening a dialog: OPEN_DIALOG buttons

A button opens a dialog when its action carries `interaction: OPEN_DIALOG`
(the only documented value):

```python
from chattice.cards import (
    Button,
    ButtonInteraction,
    ButtonList,
    Card,
    CardHeader,
    Section,
    TextInput,
    TextParagraph,
)

card = Card(
    header=CardHeader(title="Contact"),
    sections=[
        Section(
            widgets=[
                TextParagraph("Add a contact"),
                TextInput(name="name", label="Имя"),
                ButtonList(
                    buttons=[
                        Button(
                            "Open form",
                            action="open.contact",
                            interaction=ButtonInteraction.OPEN_DIALOG,
                        )
                    ]
                ),
            ]
        )
    ],
)
```

Clicking the button produces a `CARD_CLICKED` interaction with
`isDialogEvent: true` and `dialogEventType: REQUEST_DIALOG` — the same
envelope family as any other card click, so it routes through
`@router.action("open.contact")`.

## Dialog response

The handler for a `REQUEST_DIALOG` returns a `Dialog` facade wrapping a
`Card` body. The integration replies with
`actionResponse.type=DIALOG` and the dialog body under `dialogAction.dialog`:

```python
from chattice.cards import Dialog, ActionStatus
from chattice.events import ActionEvent
from chattice import Router

router = Router()


@router.action("open.contact")
async def open_dialog(action: ActionEvent) -> Dialog:
    return Dialog(
        body=Card(sections=[Section(widgets=[TextInput(name="name", label="Имя")])])
    )
```

Response JSON:

```json
{
  "actionResponse": {
    "type": "DIALOG",
    "dialogAction": {"dialog": {"body": {"sections": [{"widgets": [{"textInput": {"name": "name", "label": "Имя"}}]}]}}}
  }
}
```

## Submitting and cancelling: dialog observers

Submitting the dialog form (or cancelling it) produces a `CARD_CLICKED`
interaction with `dialogEventType: SUBMIT_DIALOG` / `CANCEL_DIALOG`. The
dispatcher routes these to dedicated observers:

- `@router.dialog_submit()` — receives an `ActionEvent` with the submitted
  values parsed into `event.form_inputs` (typed `FormInputs` mapping:
  `StringInput`, `DateInput`, `DateTimeInput`, `TimeInput`);
- `@router.dialog_cancel()` — receives the same `ActionEvent` shape; returning
  `None` yields an empty 200 (the dialog closes silently).

### actionStatus: OK and INVALID_ARGUMENT

A submit handler returns an `ActionStatus` facade — the only two documented
codes are `OK` and `INVALID_ARGUMENT`:

```python
@router.dialog_submit()
async def submit(event: ActionEvent) -> ActionStatus:
    if not event.form_inputs["name"].values:
        return ActionStatus.invalid("Имя обязательно")
    return ActionStatus.ok("Saved")
```

- `ActionStatus.ok(message)` → `{"statusCode": "OK", "userFacingMessage": ...}`
  (message optional) — the dialog closes.
- `ActionStatus.invalid(message)` → `{"statusCode": "INVALID_ARGUMENT", "userFacingMessage": ...}` — the dialog stays open showing the message.

Both serialize under `actionResponse.dialogAction.actionStatus`.

## App Home: pushCard and updateCard

The App Home tab is served through the **wrapped envelope** family: the
interaction body nests under `"chat"` and the common data under
`"commonEventObject"` instead of the direct `"type"`/`"common"` keys (the
Phase 2 envelope normalizer accepts both).

- `APP_HOME` (user opens the bot's Home tab) → `@router.app_home()` returns a
  `Card`; the integration replies with a **RenderActions** response
  `action.navigations[].pushCard`.
- `SUBMIT_FORM` (a form on the home card is submitted) →
  `@router.form_submit()` returns a `Card`; the integration replies with
  `action.navigations[].updateCard`.

```python
@router.app_home()
async def home(event: AppHomeEvent) -> Card:
    return Card(
        header=CardHeader(title="Home"),
        sections=[Section(widgets=[TextParagraph("Welcome")])],
    )


@router.form_submit()
async def update(event: FormSubmitEvent) -> Card:
    return Card(
        header=CardHeader(title="Home"),
        sections=[Section(widgets=[TextParagraph("Welcome")])],
    )
```

Response JSON for `APP_HOME`:

```json
{
  "action": {
    "navigations": [
      {"pushCard": {"header": {"title": "Home"}, "sections": [{"widgets": [{"textParagraph": {"text": "Welcome"}}]}]}}
    ]
  }
}
```

## Restrictions

These surfaces are constrained by the Google Chat platform; the framework
serializes what the docs allow, so keep the platform rules in mind:

- **Dialogs are interaction-only.** A `Dialog` response is only valid for a
  dialog `ActionEvent` (`REQUEST_DIALOG`/`SUBMIT_DIALOG`/`CANCEL_DIALOG`);
  the integration rejects `Dialog`/`ActionStatus` returns from other event
  types with a 500.
- **Dialog visibility is opener-only.** A dialog is shown only to the user
  who triggered it; there is no way to send a dialog to someone else.
- **`UPDATE_MESSAGE` is bot-only.** Replacing a card via `UPDATE_MESSAGE` is
  only permitted when the message sender type is `BOT`. Updating cards on
  human messages uses `UPDATE_USER_MESSAGE_CARDS` (implemented,
  sender-derived) — see [cards](cards.md).
- **App Home is configured separately.** The Home tab URL must be set in the
  Google Chat app configuration (Apps Script / Cloud Console); the framework
  only serves the endpoint once traffic reaches it. App Home interactions
  carry a private DM `space` and are only sent to the individual user.
