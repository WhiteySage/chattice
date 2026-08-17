# Forms vs FSM vs Scenes

Status: **Doctrine** (fixed before public beta).

The canonical rule:

    Forms collect data.
    FSM remembers durable workflow state.
    Scenes organize longer workflows.

## Forms — collect data in ONE interaction

A Google Chat dialog/form collects several fields at once. The user
fills the fields and submits; the app receives typed inputs in a single
`SUBMIT_DIALOG` event.

```python
@dataclass
class RegistrationForm(FormModel):
    name: StringInput
    email: StringInput
    department: StringInput


@router.dialog_submit(RegistrationForm.filter())
async def submit(event: ActionEvent, form: RegistrationForm) -> ActionStatus:
    return ActionStatus.ok(f"Сохранено: {form.name.values[0]}")
```

Use Forms when: the data is collected in one sitting, the fields are
known upfront, and nothing needs to survive beyond the submit.

## FSM — remember durable workflow state

FSM stores state that must survive across messages, users, time,
external callbacks, restarts, or long-running approval flows. Use it
when the workflow CANNOT be one interaction: approval chains, external
API callbacks, multi-session processes.

```python
class RequestFlow(StatesGroup):
    pending_approval = State()
    done = State()


# after the form submit:
await storage.compare_and_set(
    key,
    expected_revision=0,
    replacement=FSMRecord(state=RequestFlow.pending_approval.state, data=...),
)
```

FSM is NOT the default for structured data collection — a Telegram-style
message-by-message registration is a migration convenience, not the
Google-native first choice (see `examples/scenarios/registration_fsm.py`
vs `registration_dialog.py`).

## Scenes — organize longer workflows

Scenes layer OVER FSM to structure long multi-step workflows (enter/
exit/fallback/timeout/reset). Planned post-beta: atomic FSM
records come first; a Scene is never a second persistence engine.

## Decision table

| Situation | Use |
| --- | --- |
| Collect N known fields in one sitting | Form / Dialog |
| One-shot submit, then done | Form only |
| State must survive restart/approval/callback | Form (collect) + FSM record (remember) |
| Telegram-style message-by-message flow must be migrated | FSM (sequential) — document the Form alternative |
| Long multi-step workflow organization | Scenes over FSM |
| Polls | APPLICATION: command → private Dialog → public Card → Actions/domain storage (not shipped/core) |

Canonical examples: `examples/scenarios/request_form.py`,
`request_form_plus_fsm.py`, `registration_fsm.py`,
`registration_dialog.py`. The Poll recipe was REMOVED (owner
2026-08-16) — polls are application-owned scenarios
assembled from the primitives.

## Cross-context FSM access (explicit keys)

A manager advancing an employee's request is ordinary application code:
address the workflow record by an EXPLICIT `StorageKey` on the record
store — never a privileged global "modify another user's FSM" operation.

```python
key = StorageKey(user="users/9", space="spaces/A", thread=None)
record = await storage.get_record(key)
await storage.compare_and_set(
    key, record.revision, FSMRecord(state="approved", data=record.data)
)
```

## Response lifecycle (sync vs deferred)

The interaction response (30 s, no auth) and authenticated `Bot` calls
are DIFFERENT channels. Handlers must answer the interaction quickly
(text/card/dialog) and move long CRM/browser/AI work into `Bot` calls —
no ack() API, no queue: the boundary IS the API split.

## Onboarding recipe (ADDED_TO_SPACE)

```python
@router.added_to_space()
async def welcome(event: AddedToSpaceEvent) -> str:
    return "Привет! Я умею: /search — поиск, «Отчёт» — выгрузка, кнопки — заявки."
```

Recipe only — onboarding is not a lifecycle engine.

## Adjacent mental models

- `return "pong"` / `InteractionResponse.respond(...)` — answer the
  CURRENT interaction (30 s, no auth). `bot.send_message(space=...)` —
  explicit proactive outbound (authenticated, any Space). They are
  different channels; Chattice never merges them.
- One-way notification to ONE Space → an incoming webhook MAY be enough.
  One app identity sending to MULTIPLE Spaces and/or handling
  interactions → full Chattice app (see `docs/guides/enterprise.md`).
- UI navigation between Cards ≠ FSM state. Dialog/Form field values ≠
  durable workflow state: a form submission becomes FSM data only when
  the workflow must survive messages/users/time/restarts.
