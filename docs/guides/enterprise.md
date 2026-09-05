# Enterprise patterns

Multi-team deployment patterns. Chattice provides the messenger
surface; business architecture (CRM/Jira/databases/schedulers) stays
application code.

## Incoming webhook vs full Chattice Chat app

**Incoming Google Chat webhook:** an external system POSTs to a webhook
URL tied to ONE configured Space. One-way notifications only; no
interaction handling; good for small alert integrations.

**Full Chattice Chat app:** one Chat app identity with proactive sends to
MANY Spaces where permitted, plus messages, Cards, files, commands,
actions, Forms/Dialogs, `bot.app.messages.update`, interactive workflows.

A CRM request that must reach two Spaces is the FULL APP pattern:

```python
await bot.app.messages.create(FINANCE_SPACE, card=request_card(request))
await bot.app.messages.create(MANAGERS_SPACE, card=request_card(request))
```

— not one webhook per Space, unless the application deliberately chooses
the simpler webhook architecture.

## Bot identities: one feature ≠ one Chat app

Do NOT force unrelated trust boundaries into one universal bot, and do
NOT split every feature into its own app either. A practical deployment
may run several independent Chat app identities — same codebase, shared
application services, separate configuration/credentials:

| Identity | Purpose | Audience / boundary |
| --- | --- | --- |
| Department Bot | menu, requests, Cards/Dialogs, local workflows | one department |
| Company Bot | company-wide workflows, broad audience | whole company |
| Alerts Bot | proactive Jira/CRM/infra sends into several Spaces | monitoring |
| Admin Bot | onboarding/offboarding, memberships | privileged, narrow |

```python
department_bot = Bot(credentials_provider=department_credentials)
alerts_bot = Bot(credentials_provider=alerts_credentials)
```

Same classes, different credentials — the framework never forces one
identity.

## One business event → multiple Spaces

One CRM event → TWO proactive sends through ONE Bot. No
NotificationService, no event bus, no queue — explicit outbound sends
are the whole feature. The outbound facade is shown in
`examples/without_dispatcher.py`; loop it over your Space list.

## Canonical patterns

- **Private configuration → public result:** private Dialog →
  `bot.app.messages.create(event.space, card=...)` — the dialog
  mechanics are in the dialog section of `examples/docs/from_zero.py`.
- **Request + approval:** form collects → FSM record remembers →
  typed ActionData approval → CRM call — the pieces are the typed form
  and dialog sections of `examples/docs/from_zero.py` plus the FSM
  workflow in `examples/finite_state_machine.py`.
- **Onboarding:** `ADDED_TO_SPACE` → welcome message → primary commands.
- **Add/remove users from Spaces:** supported only where Google provides
  the capability — raw SDK escape hatch until a wrapper earns its place.

## Framework vs application responsibility

| Chattice | Application |
| --- | --- |
| routing, events, typed forms/actions | CRM/ERP/Jira clients |
| FSM records, cards, transports | business rules, DB schemas |
| verification, capability guards | identity/authorization policy |
| testing toolkit | schedulers, queues, alert logic |
