"""F04 regression: single-flight init and linearizable close.

Deterministic barriers (threading.Event inside the provider, async
Events for scheduling) — no sleeps as synchronization.
"""

from __future__ import annotations

import asyncio
import threading

from google.auth.credentials import AnonymousCredentials

from chattice.client import Bot, ChatAPIError

from ._fake_transport import FakeChatTransport


def _creds() -> AnonymousCredentials:
    return AnonymousCredentials()  # type: ignore[no-untyped-call]


class _BlockingProvider:
    """Counts invocations and blocks inside the worker thread until released."""

    def __init__(self) -> None:
        self.calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self) -> AnonymousCredentials:
        self.calls += 1
        self.entered.set()
        self.release.wait(timeout=5)
        return _creds()


async def test_concurrent_first_sends_resolve_provider_once() -> None:
    """F04 probe: two concurrent sends -> the provider runs exactly once."""
    provider = _BlockingProvider()
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)

    first = asyncio.create_task(bot.send_message("spaces/AAA", text="a"))
    second = asyncio.create_task(bot.send_message("spaces/AAA", text="b"))
    await asyncio.to_thread(provider.entered.wait, 5)
    await asyncio.sleep(0.05)  # let the second call reach the shared task
    assert provider.calls == 1  # single-flight: no second provider call
    provider.release.set()
    await asyncio.gather(first, second)
    assert provider.calls == 1
    assert bot._client is not None  # one client shared by both sends


async def test_close_during_construction_publishes_no_client() -> None:
    """Close while the provider is still running: no client may appear
    after terminal close, and the in-flight send fails closed."""
    provider = _BlockingProvider()
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)

    send = asyncio.create_task(bot.send_message("spaces/AAA", text="x"))
    await asyncio.to_thread(provider.entered.wait, 5)
    close = asyncio.create_task(bot.close())
    await asyncio.sleep(0.05)  # close has begun and is waiting on init
    assert bot._closed
    provider.release.set()
    await close
    try:
        await send
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError from the aborted send")
    assert bot._client is None  # construction never published a client
    assert transport.requests == []


async def test_close_before_first_use_blocks_all_calls() -> None:
    provider = _BlockingProvider()
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)
    await bot.close()
    try:
        await bot.send_message("spaces/AAA", text="x")
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError after close")
    assert provider.calls == 0  # no provider work after terminal close
    assert transport.requests == []


async def test_provider_failure_is_retryable() -> None:
    """A failed resolution is not cached: the next call re-invokes the
    provider (pinned contract — errors stay retryable)."""
    calls = 0

    def flaky_provider() -> AnonymousCredentials:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("token refresh down")
        return _creds()

    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=flaky_provider, transport=transport)
    try:
        await bot.send_message("spaces/AAA", text="x")
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected the provider failure to surface")
    await bot.send_message("spaces/AAA", text="x")  # retry succeeds
    assert calls == 2


async def test_close_linearizes_with_inflight_resolution() -> None:
    """close() waits for in-flight resolution/construction to FINISH
    before returning: the aborted send fails closed and no client is
    published, but close's return is ordered after the shared work."""
    provider = _BlockingProvider()
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)

    send = asyncio.create_task(bot.send_message("spaces/AAA", text="x"))
    await asyncio.to_thread(provider.entered.wait, 5)
    close = asyncio.create_task(bot.close())
    await asyncio.sleep(0.05)
    assert not close.done()  # close is still coordinating with the send
    provider.release.set()
    await close
    try:
        await send
    except ChatAPIError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ChatAPIError from the aborted send")
    assert bot._client is None  # terminal close never publishes a client


async def test_cancelled_waiter_does_not_kill_shared_init() -> None:
    """Shield semantics: cancelling one waiter leaves the shared
    construction running for the others."""
    provider = _BlockingProvider()
    transport = FakeChatTransport(credentials=_creds())
    bot = Bot(credentials_provider=provider, transport=transport)

    cancelled = asyncio.create_task(bot.send_message("spaces/AAA", text="c"))
    await asyncio.to_thread(provider.entered.wait, 5)
    cancelled.cancel()
    with __import__("pytest").raises(asyncio.CancelledError):
        await cancelled
    provider.release.set()
    # a fresh call succeeds: the shared task survived the cancellation
    await bot.send_message("spaces/AAA", text="ok")
    assert provider.calls == 1
    assert len(transport.requests) == 1
