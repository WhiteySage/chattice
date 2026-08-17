# Installation

Chattice requires Python 3.11 or newer.

## Create a project

With `uv`:

```bash
mkdir hello-chattice
cd hello-chattice
uv init --python 3.11
uv add "chattice[fastapi]" uvicorn
```

With the standard library and `pip`:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install "chattice[fastapi]" uvicorn
```

Optional extras are independent:

| Extra | Use it for |
| --- | --- |
| `fastapi` | HTTP, Pub/Sub push, and Workspace Events push endpoints |
| `pubsub` | Pub/Sub streaming-pull ingress |
| `redis` | Redis FSM and idempotency storage |
| `gemini` | Experimental Google Gen AI adapter |

Do not install the `gemini` extra for a normal Chat app. AI support is outside
stable core.

## Verify the environment

```bash
python -c "import chattice; print(chattice.__version__)"
```

The output for this documentation line is `0.14.0b1`.

Next: [5-minute Quickstart](quickstart.md).
