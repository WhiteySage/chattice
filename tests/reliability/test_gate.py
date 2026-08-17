"""Adversarial gate: redelivery dedupe and storage failure."""

from __future__ import annotations

import base64
import json
from typing import cast

import httpx
from fastapi import FastAPI

from chattice import Dispatcher, Router
from chattice.events import MessageEvent
from chattice.idempotency import IdempotencyStorage, MemoryIdempotencyStorage
from chattice.integrations.fastapi import create_pubsub_router


def _interaction() -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-15T10:00:00Z",
        "message": {"text": "ping"},
        "user": {"name": "users/1"},
        "space": {"name": "spaces/AAA"},
    }


def _body(message_id: str) -> dict[str, object]:
    raw = json.dumps(_interaction()).encode()
    return {
        "message": {
            "data": base64.b64encode(raw).decode(),
            "messageId": message_id,
        },
        "subscription": "projects/p/subscriptions/s",
    }


async def test_duplicate_delivery_dispacted_once() -> None:
    router = Router()
    seen = 0

    @router.message()
    async def handler(message: MessageEvent) -> str:
        nonlocal seen
        seen += 1
        return "x"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_pubsub_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=MemoryIdempotencyStorage(),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/pubsub", json=_body("m-1"))
        second = await client.post("/pubsub", json=_body("m-1"))
    assert first.status_code == 204
    assert second.status_code == 204
    assert seen == 1  # the duplicate was absorbed before dispatch


class _FailingStorage:
    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> object:
        raise RuntimeError("redis down")

    async def complete(self, key: str, *, owner: str) -> None:
        return None

    async def release(self, key: str, *, owner: str) -> None:
        return None

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        return True


async def test_storage_failure_returns_500() -> None:
    app = FastAPI()
    app.include_router(
        create_pubsub_router(
            Dispatcher(),
            allow_unverified=True,
            idempotency_storage=cast(IdempotencyStorage, _FailingStorage()),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_body("m-1"))
    assert result.status_code == 500


async def test_handler_failure_releases_claim_and_redelivery_redispatches() -> None:
    """A failed dispatch must NOT be treated as completed: the claim is
    released, so Pub/Sub redelivery re-dispatches the handler (at-least-once
    semantics preserved instead of silently losing the work)."""
    router = Router()
    attempts = 0

    @router.message()
    async def handler(message: MessageEvent) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("first attempt fails")
        return "recovered"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_pubsub_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=MemoryIdempotencyStorage(),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/pubsub", json=_body("m-1"))
        redelivered = await client.post("/pubsub", json=_body("m-1"))
    assert first.status_code == 500
    assert redelivered.status_code == 204
    assert attempts == 2  # the redelivery was NOT absorbed as a duplicate


async def test_success_keeps_claim_and_duplicate_is_absorbed() -> None:
    """The success path keeps the record: a genuine duplicate after success
    is absorbed with 204 (complete)."""
    router = Router()
    attempts = 0

    @router.message()
    async def handler(message: MessageEvent) -> str:
        nonlocal attempts
        attempts += 1
        return "ok"

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_pubsub_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=MemoryIdempotencyStorage(),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/pubsub", json=_body("m-1"))
        duplicate = await client.post("/pubsub", json=_body("m-1"))
    assert first.status_code == 204
    assert duplicate.status_code == 204
    assert attempts == 1


class _ClearFailingStorage:
    def __init__(self) -> None:
        from chattice.idempotency import ClaimResult

        self.ClaimResult = ClaimResult

    async def claim(self, key: str, *, owner: str, lease_seconds: float) -> object:
        return self.ClaimResult.FIRST

    async def complete(self, key: str, *, owner: str) -> None:
        return None

    async def release(self, key: str, *, owner: str) -> None:
        raise RuntimeError("redis down on release")

    async def renew(self, key: str, *, owner: str, lease_seconds: float) -> bool:
        return True


async def test_release_failure_still_returns_500() -> None:
    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        raise RuntimeError("handler fails; release will also fail")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(
        create_pubsub_router(
            dispatcher,
            allow_unverified=True,
            idempotency_storage=cast(IdempotencyStorage, _ClearFailingStorage()),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/pubsub", json=_body("m-1"))
    assert result.status_code == 500
