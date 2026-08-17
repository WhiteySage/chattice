#!/usr/bin/env bash
# Reproducible package verification: fresh venv -> wheel install -> smoke tests.
set -euo pipefail

cd "$(dirname "$0")/.."

# The package requires Python >= 3.11; the system python3 is often older.
if [ -z "${PYTHON:-}" ]; then
  if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  else
    FOUND=$(uv python find 2>/dev/null | head -1 || true)
    PYTHON="${FOUND:-$(command -v python3 || command -v python)}"
  fi
fi

rm -f dist/chattice-*.whl dist/chattice-*.tar.gz
uv build

TMP_VENV="$(mktemp -d)"
trap 'rm -rf "$TMP_VENV"' EXIT

"$PYTHON" -m venv "$TMP_VENV"
# Dependencies (google-apps-chat, google-auth, pydantic) come from PyPI; the
# freshly built wheel comes from dist/.
"$TMP_VENV/bin/pip" install --quiet "$(ls dist/chattice-*.whl | head -1)"

# Installed-package guarantee: the import must resolve into the fresh venv,
# never the source tree.
"$TMP_VENV/bin/python" -c 'import chattice, sys; assert chattice.__file__.startswith(sys.prefix), chattice.__file__'

# Smoke: import from the installed wheel (NOT the source tree) and run a
# mini-scenario through the public API.
cd /tmp
"$TMP_VENV/bin/python" - <<'PY'
import chattice
from chattice import Dispatcher, Router
from chattice.adapters.google_chat import parse_interaction
from chattice.testing import MockBot

assert chattice.__version__.startswith("0.14.0"), chattice.__version__

router = Router()

@router.message()
async def echo(message, bot: MockBot):
    await bot.send_message(message.space, text=message.text)
    return "handled"

dispatcher = Dispatcher()
dispatcher.include_router(router)

import asyncio

payload = {
    "type": "MESSAGE",
    "eventTime": "2026-08-15T10:00:00Z",
    "message": {"text": "ping"},
    "user": {"name": "users/1"},
    "space": {"name": "spaces/AAA"},
}

async def main():
    bot = MockBot()
    result = await dispatcher.feed_update(parse_interaction(payload), bot=bot)
    assert result == "handled"
    bot.assert_message_sent("ping")

asyncio.run(main())
print("wheel smoke OK:", chattice.__version__)
PY
