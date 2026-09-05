# Examples

Flat, self-contained, LIVE examples mirroring the aiogram example set,
adapted to Google Chat semantics. The repo ships NO credentials — each
example reads YOUR environment, so copy one into your project, point it
at your service account, and it runs for real:

```bash
pip install "chattice[pubsub]"
export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
export CHATTICE_SUBSCRIPTION="projects/PROJECT/subscriptions/SUBSCRIPTION"
python examples/echo_bot.py
```

- `CHATTICE_SERVICE_ACCOUNT_FILE` — path to YOUR service account JSON
  (`chat.bot` scope; plus Pub/Sub Subscriber on the subscription for the
  pull examples).
- `CHATTICE_SUBSCRIPTION` — full pull subscription name for the Pub/Sub
  examples.
- `CHATTICE_AUDIENCE` — your HTTP Authentication Audience for the
  webhook example.

The pull examples use the service-account file twice: `chat.bot` scopes for
outbound Chat calls and Pub/Sub scopes for the subscriber. The account also
needs the Pub/Sub Subscriber IAM role on the subscription. The examples pass
both providers explicitly; they do not depend on a separate ADC setup.

For the webhook example, install `chattice[fastapi]` and `uvicorn`, then run:

```bash
export CHATTICE_AUDIENCE="https://chat.example.com/"
python -m uvicorn examples.echo_bot_webhook:app --port 8000
```

The webhook only sends synchronous responses and needs no outbound service
account. Its public HTTPS endpoint must match the configured audience.

CI imports the examples and exercises pull startup, handlers, and shutdown
with a stubbed subscriber, without Google calls. `examples/docs/from_zero.py`
is the credential-free tour through the real parser and Dispatcher with MockBot.

| aiogram example | chattice example | What it shows |
| --- | --- | --- |
| `echo_bot.py` | `echo_bot.py` | Echo over Pub/Sub streaming pull — the "polling" bot |
| `echo_bot_webhook.py` | `echo_bot_webhook.py` | The same echo behind a verified HTTP (FastAPI) webhook |
| `error_handling.py` | `error_handling.py` | Error observers answer safely; no observer → nack/redelivery |
| `finite_state_machine.py` | `finite_state_machine.py` | Multi-step Incident workflow (`StatesGroup` + `StateFilter`) |
| `own_filter.py` | `own_filter.py` | Async predicate functions as first-class filters |
| `specify_updates.py` | `specify_updates.py` | Magic filters (`F`) pick which handler serves an event |
| `context_addition_from_filter.py` | `context_addition_from_filter.py` | A filter enriches the dispatch context; handlers get values injected by name |
| `without_dispatcher.py` | `without_dispatcher.py` | The outbound `Bot` facade used directly — proactive sends and CRUD, no dispatcher |

aiogram examples without a Google Chat counterpart here:
`scene.py` / `quiz_scene.py` (no Scene API), `stars_invoice.py` (no
payments), `echo_bot_webhook_ssl.py` (TLS is a uvicorn deployment
concern), and `multibot.py` (identity is chosen explicitly through
`bot.app` / `bot.user` instead of multiple bot tokens).

Google Chat capabilities aiogram does not have — cards, dialogs, forms,
Pub/Sub ingress, App Home, Workspace Events — are covered by the
documented full tour in `examples/docs/from_zero.py` and the guides.
