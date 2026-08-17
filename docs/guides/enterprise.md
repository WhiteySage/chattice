# Enterprise patterns

Internal-company deployment patterns. Chattice provides the messenger
surface; business architecture (CRM/Jira/databases/schedulers) stays
application code.

## Incoming webhook vs full Chattice Chat app

**Incoming Google Chat webhook:** an external system POSTs to a webhook
URL tied to ONE configured Space. One-way notifications only; no
interaction handling; good for small alert integrations.

**Full Chattice Chat app:** one Chat app identity with proactive sends to
MANY Spaces where permitted, plus messages, Cards, files, commands,
actions, Forms/Dialogs, `update_message`, interactive workflows.

A CRM request that must reach two Spaces is the FULL APP pattern:

```python
await bot.send_message(space=FINANCE_SPACE, card=request_card(request))
await bot.send_message(space=MANAGERS_SPACE, card=request_card(request))
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
department_bot = Bot(
    credentials_provider=ServiceAccountCredentialsProvider.from_service_account_file(
        "dept-sa.json"
    )
)
alerts_bot = Bot(
    credentials_provider=ServiceAccountCredentialsProvider.from_service_account_file(
        "alerts-sa.json"
    )
)
```

Same classes, different credentials — the framework never forces one
identity.

## One business event → multiple Spaces

`examples/production/multi_space_notification.py`: a CRM event produces
TWO proactive sends through ONE Bot. No NotificationService, no event
bus, no queue — explicit outbound sends are the whole feature
(charter: deliberately not building a notification subsystem).

## Canonical patterns

- **Private configuration → public result:** private Dialog →
  `bot.send_message(space=event.space, card=...)`
  (`examples/scenarios/private_dialog_to_public_card.py`).
- **Request + approval:** form collects → FSM record remembers →
  typed ActionData approval → CRM call
  (`examples/production/crm_workflow/main.py` — illustrative sketch).
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
