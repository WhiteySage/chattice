# Executable examples

Every canonical example runs without Google credentials and is executed by
pytest. Live integration tests are separate and opt-in.

| Task | Example |
| --- | --- |
| Full documented example | `examples/docs/from_zero.py` |
| Hello/echo and outbound MockBot | `examples/bots/echo_bot.py` |
| Slash and quick commands | `examples/bots/command_bot.py` |
| Cards and named actions | `examples/bots/buttons_bot.py` |
| Form input and validation | `examples/bots/form_bot.py` |
| Dialog open and submit | `examples/bots/dialog_bot.py` |
| FSM | `examples/bots/fsm_bot.py` |
| FastAPI HTTP assembly | `examples/bots/fastapi_bot.py` |
| Pub/Sub push envelope | `examples/bots/pubsub_bot.py` |
| Pub/Sub streaming pull (echo, run it) | `examples/bots/pubsub_pull_echo_bot.py` |
| Workspace Events | `examples/bots/workspace_events_bot.py` |
| App Home | `examples/scenarios/apphome_dashboard.py` |
| Link preview | `examples/scenarios/link_preview.py` |
| Private dialog to public card | `examples/scenarios/private_dialog_to_public_card.py` |
| Multi-Space proactive send | `examples/production/multi_space_notification.py` |
| Local files & media (copy-paste recipes) | [`docs/guides/files-media.md`](guides/files-media.md), [Cookbook](cookbook/recipes.md) |
| Regex routing (copy-paste recipes) | [`docs/guides/routing-state.md`](guides/routing-state.md) |

Media upload needs USER authentication (no-credential execution is not
meaningful), so media flows ship as copy-paste recipes with MockBot
exercisable in unit tests instead of a credential-free executable.

Run one from a checkout:

```bash
python examples/docs/from_zero.py
```

For an application using an installed package, copy the relevant example into
your project and replace synthetic payloads/`MockBot` with the HTTP integration
and real `Bot` configuration from Getting Started. The example's imports are
all public API.

Poll, approval, incident, and AI assistant remain application recipes. They
are not framework primitives.
