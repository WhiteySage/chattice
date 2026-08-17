"""Phase gate: an application test mocks zero Google internals."""

from __future__ import annotations

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.testing import EventFactory, MockBot


async def test_application_handler_with_mock_bot() -> None:
    bot = MockBot()
    router = Router()

    @router.message()
    async def echo(message: MessageEvent, bot: MockBot) -> str:
        await bot.send_message(message.space, text=message.text)
        return "handled"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    result = await dispatcher.feed_update(EventFactory.message("ping"), bot=bot)
    assert result == "handled"
    bot.assert_message_sent("ping")
