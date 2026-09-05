"""Proactive sends without a dispatcher: copy, set YOUR env, run.

No router, no events — the `Bot` resource facade on its own: create,
update, read, and delete a message in YOUR Space. The example cleans up
after itself (deletes what it sent).

Environment (yours, not committed anywhere):

    CHATTICE_SERVICE_ACCOUNT_FILE  path to YOUR service account JSON
                                   (chat.bot scope, Space access)

Run:
    pip install chattice
    export CHATTICE_SERVICE_ACCOUNT_FILE=/path/to/your-sa.json
    python examples/without_dispatcher.py spaces/AAAAXXXX
"""

from __future__ import annotations

import asyncio
import os
import sys

from chattice.auth import ServiceAccountCredentialsProvider
from chattice.client import Bot


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}=<value> before running this example")
    return value


async def main() -> None:
    space = sys.argv[1] if len(sys.argv) > 1 else ""
    if not space:
        raise SystemExit("usage: python examples/without_dispatcher.py spaces/AAAAXXXX")

    bot = Bot(
        app_credentials_provider=(
            ServiceAccountCredentialsProvider.from_service_account_file(
                _require_env("CHATTICE_SERVICE_ACCOUNT_FILE")
            )
        )
    )
    try:
        # 1. proactive text into YOUR Space (no incoming interaction)
        sent = await bot.app.messages.create(
            space, text="proactive: hello from chattice"
        )
        print(f"1. created  -> {sent.name}")

        # 2. update the same message by name
        updated = await bot.app.messages.update(sent.name, text="proactive: v2")
        print(f"2. updated  -> {updated.name}")

        # 3. read it back
        fetched = await bot.app.messages.get(sent.name)
        print(f"3. fetched  -> {fetched.name}")

        # 4. delete the message
        await bot.app.messages.delete(sent.name)
        print(f"4. deleted  -> {sent.name}")
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
