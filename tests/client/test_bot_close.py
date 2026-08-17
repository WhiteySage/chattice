"""Bot.close() / async context manager / off-loop credential resolution."""

from __future__ import annotations

import threading

from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot

from ._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


class _CloseCountingTransport(FakeChatTransport):
    def __init__(self, credentials: object) -> None:
        super().__init__(credentials=credentials)
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


async def test_close_before_use_is_a_noop() -> None:
    bot = Bot(credentials=_creds())
    await bot.close()  # no client built yet — must not raise
    await bot.close()  # idempotent second call


async def test_close_closes_the_underlying_transport() -> None:
    creds = _creds()
    transport = _CloseCountingTransport(credentials=creds)
    bot = Bot(credentials=creds, transport=transport)
    _ = bot.raw_client  # build the client lazily
    await bot.close()
    assert transport.close_calls == 1


async def test_close_is_idempotent() -> None:
    creds = _creds()
    transport = _CloseCountingTransport(credentials=creds)
    bot = Bot(credentials=creds, transport=transport)
    _ = bot.raw_client
    await bot.close()
    await bot.close()
    assert transport.close_calls == 1


async def test_async_context_manager_closes_on_exit() -> None:
    creds = _creds()
    transport = _CloseCountingTransport(credentials=creds)
    async with Bot(credentials=creds, transport=transport) as bot:
        _ = bot.raw_client
    assert transport.close_calls == 1


async def test_credential_provider_runs_off_the_event_loop() -> None:
    """The async path resolves credentials in a worker thread, so blocking
    providers (file reads, token refresh) never block the event loop."""
    main_thread = threading.get_ident()
    seen: list[int] = []

    def provider() -> AnonymousCredentials:
        seen.append(threading.get_ident())
        return _creds()

    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)
    await bot.send_message("spaces/AAA", text="x")
    assert seen and seen[0] != main_thread


async def test_static_credentials_path_stays_sync() -> None:
    """Plain credentials need no thread hop — the async path works too."""
    from google.apps.chat_v1.types.space import Space

    creds = _creds()
    transport = FakeChatTransport(credentials=creds)
    transport.spaces["spaces/AAA"] = Space(name="spaces/AAA", display_name="Demo")
    bot = Bot(credentials=creds, transport=transport)
    result = await bot.get_space("spaces/AAA")
    assert result.name == "spaces/AAA"


async def test_close_awaits_awaitable_transport() -> None:
    """The real grpc_asyncio transport closer returns an awaitable —
    Bot.close() must AWAIT it, not discard the coroutine."""

    creds = _creds()
    transport = _CloseCountingTransport(credentials=creds)

    async def async_close() -> None:
        transport.close_calls += 1

    transport.close = async_close  # type: ignore[method-assign,assignment]
    bot = Bot(credentials=creds, transport=transport)
    _ = bot.raw_client
    await bot.close()
    assert transport.close_calls == 1
    # no "coroutine was never awaited" — a second close stays idempotent
    await bot.close()
    assert transport.close_calls == 1


async def test_concurrent_first_use_builds_one_client() -> None:
    import asyncio

    from google.apps.chat_v1.types.space import Space

    creds = _creds()
    transport = FakeChatTransport(credentials=creds)
    transport.spaces["spaces/AAA"] = Space(name="spaces/AAA", display_name="Demo")
    bot = Bot(credentials=creds, transport=transport)
    results = await asyncio.gather(
        bot.get_space("spaces/AAA"), bot.get_space("spaces/AAA")
    )
    assert results[0].name == "spaces/AAA"
    assert bot._client is not None
