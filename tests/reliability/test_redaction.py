"""Source scan: logging never carries secrets; no pickle/eval anywhere."""

from __future__ import annotations

import pathlib
import re

import pytest

_FORBIDDEN = (
    "authorization",
    "bearer",
    "private_key",
    "client_secret",
    "refresh_token",
)
_LOG_CALL = re.compile(r"\.(info|exception|warning|error|debug)\(")


def test_no_secret_logging_in_src() -> None:
    src = pathlib.Path("src")
    offenders: list[str] = []
    for path in src.rglob("*.py"):
        lines = path.read_text().splitlines()
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not _LOG_CALL.search(stripped):
                continue
            lowered = stripped.lower()
            if "token" in lowered or any(word in lowered for word in _FORBIDDEN):
                offenders.append(f"{path}:{number}: {stripped}")
    assert offenders == []


def test_no_pickle_or_eval_in_src() -> None:
    src = pathlib.Path("src")
    offenders: list[str] = []
    for path in src.rglob("*.py"):
        text = path.read_text()
        if "pickle" in text or "eval(" in text:
            offenders.append(str(path))
    assert offenders == []


async def test_handler_exception_messages_never_reach_logs() -> None:
    """B3 regression: handler/verifier/storage exception MESSAGES can carry
    secrets (tokens, form values); framework logs must carry the exception
    CLASS only."""
    import logging

    import httpx
    from fastapi import FastAPI

    from chattice import Dispatcher, Router
    from chattice.events import MessageEvent
    from chattice.integrations.fastapi import create_chat_router
    from chattice.transports.http import MockVerifier

    router = Router()

    @router.message()
    async def handler(message: MessageEvent) -> str:
        raise RuntimeError("refresh_token=super-secret-value")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))

    captured: list[logging.LogRecord] = []
    logger = logging.getLogger("chattice.http")

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler_ref = _Capture()
    logger.addHandler(handler_ref)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = await client.post(
                "/",
                json={
                    "type": "MESSAGE",
                    "message": {"text": "hi"},
                    "user": {"name": "users/1"},
                    "space": {"name": "spaces/A"},
                },
            )
        assert result.status_code == 500
    finally:
        logger.removeHandler(handler_ref)
    logged = "\n".join(record.getMessage() for record in captured)
    assert "super-secret-value" not in logged
    assert "refresh_token" not in logged


async def test_verifier_exception_messages_never_reach_logs() -> None:
    """S2 regression: verifier failures must log the CLASS only."""
    import logging

    import httpx
    from fastapi import FastAPI

    from chattice import Dispatcher
    from chattice.integrations.fastapi import create_chat_router
    from chattice.transports.http.errors import VerificationError

    class _LeakyVerifier:
        def verify(self, request: object) -> None:
            raise VerificationError("refresh_token=verifier-secret")

    captured: list[logging.LogRecord] = []
    logger = logging.getLogger("chattice.http")

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler_ref = _Capture()
    logger.addHandler(handler_ref)
    try:
        app = FastAPI()
        app.include_router(create_chat_router(Dispatcher(), _LeakyVerifier()))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = await client.post(
                "/",
                json={
                    "type": "MESSAGE",
                    "message": {"text": "hi"},
                    "user": {"name": "users/1"},
                    "space": {"name": "spaces/A"},
                },
            )
        assert result.status_code == 401
    finally:
        logger.removeHandler(handler_ref)
    logged = "\n".join(record.getMessage() for record in captured)
    assert "verifier-secret" not in logged
    assert "refresh_token" not in logged


async def test_lifespan_close_errors_log_class_only() -> None:
    """S2 regression: lifecycle resource failures must not leak messages."""
    import logging

    from chattice import Dispatcher

    class _Resource:
        async def start(self) -> None:
            return None

        async def close(self) -> None:
            raise RuntimeError("refresh_token=lifecycle-secret")

    captured: list[logging.LogRecord] = []
    logger = logging.getLogger("chattice.lifespan")

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler_ref = _Capture()
    logger.addHandler(handler_ref)
    try:
        with pytest.raises(RuntimeError):
            async with Dispatcher().lifespan(_Resource()):
                pass
    finally:
        logger.removeHandler(handler_ref)
    logged = "\n".join(record.getMessage() for record in captured)
    assert "lifecycle-secret" not in logged
