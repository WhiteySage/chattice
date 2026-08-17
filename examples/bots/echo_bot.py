"""Echo bot: MessageEvent in, exactly one send_message out (no network).

The whole loop is exercised with the `chattice.testing` toolkit: an
`EventFactory.message("ping")` builds the incoming event, the handler replies
through the injected `MockBot`, and `assert_message_sent` verifies the exact
outgoing call — no raw Google JSON and no HTTP involved.

Run:
    python examples/bots/echo_bot.py
"""

from __future__ import annotations

import asyncio

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.testing import EventFactory, MockBot


async def main() -> None:
    bot = MockBot()
    router = Router()

    @router.message()
    async def echo(message: MessageEvent, bot: MockBot) -> str:
        await bot.send_message(message.space, text=message.text)
        return "handled"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(EventFactory.message("ping"), bot=bot)
    bot.assert_message_sent("ping")
    print(f"echo result={result!r} sent={bot.calls}")


if __name__ == "__main__":
    asyncio.run(main())
