# Recommended project structure

Start with one module. Split by feature when handlers and dependencies grow:

```text
my_chat_app/
├── app.py                 # FastAPI composition and lifespan
├── config.py              # environment parsing, no global credentials
├── bot.py                 # Bot and credential provider construction
├── routers/
│   ├── messages.py
│   ├── commands.py
│   └── cards.py
├── workspace_events.py    # separate EventsRouter tree
├── services/              # application/business logic
└── tests/
```

Routers depend on application services through handler dependency injection.
Business entities such as polls, approvals, incidents, and AI assistants stay
in application modules; they are recipes composed from Chattice primitives.

Keep transport assembly at the edge, handlers thin, and raw Google access
localized. Use `Dispatcher.lifespan(...)` for resources that must start and
close with the application.

Next: [Mental model](../concepts/mental-model.md).
