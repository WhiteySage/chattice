# Examples

All canonical examples expose an async `main()` and run without Google
credentials. `tests/test_examples.py` and `tests/test_documentation_examples.py`
execute them in CI, while `python -m compileall` and Ruff cover the entire
directory.

Start with the complete documentation acceptance journey:

```bash
python examples/docs/from_zero.py
```

It covers hello, synchronous reply, contextual reply, Thread continuation,
top-level and private sends, a native slash command, a card button/action, a
typed form, a dialog, and a Workspace Event using only public APIs.

Focused examples:

- `bots/echo_bot.py` — message + MockBot.
- `bots/command_bot.py` — slash and quick commands.
- `bots/buttons_bot.py` — Card and named Action.
- `bots/form_bot.py` — form inputs and `ActionStatus`.
- `bots/dialog_bot.py` — dialog request and submit.
- `bots/fsm_bot.py` — state machine.
- `bots/fastapi_bot.py` — HTTP endpoint assembly.
- `bots/pubsub_bot.py` — Pub/Sub interaction path.
- `bots/workspace_events_bot.py` — separate resource-event path.
- `scenarios/` — App Home, links, typed forms, and multi-step workflows.
- `production/` — multi-Space and larger application composition.

Synthetic payloads are documented or sanitized fixture shapes and exercise the
real parser/dispatcher. Replace `MockBot` and synthetic delivery with the
Getting Started HTTP and credential setup when deploying.
