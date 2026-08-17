"""End-to-end HTTP interaction path through the FastAPI integration."""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from starlette.applications import Starlette

from chattice import Dispatcher, Router
from chattice.capabilities import ResponseCapabilities, ResponseCapability
from chattice.events import MessageEvent, RemovedFromSpaceEvent
from chattice.integrations.fastapi import create_chat_router
from chattice.transports.http import (
    IncomingRequest,
    InteractionResponse,
    MockVerifier,
    VerificationError,
)


def _message_payload(text: str) -> dict[str, object]:
    return {
        "type": "MESSAGE",
        "eventTime": "2026-08-13T12:35:00Z",
        "message": {"text": text},
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
    }


def _build_app(dispatcher: Dispatcher, *, reject: bool = False) -> FastAPI:
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier(reject=reject)))
    return app


def _echo_dispatcher() -> Dispatcher:
    router = Router()

    @router.message()
    async def echo(message: MessageEvent, response: InteractionResponse) -> str:
        return message.text

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def test_full_path_returns_text_message() -> None:
    app = _build_app(_echo_dispatcher())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.json() == {"text": "ping"}


async def test_handler_respond_short_circuits_return_value() -> None:
    router = Router()

    @router.message()
    async def echo(message: MessageEvent, response: InteractionResponse) -> None:
        response.respond("explicit")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.json() == {"text": "explicit"}


async def test_dict_payload_passes_through() -> None:
    router = Router()

    @router.message()
    async def echo(message: MessageEvent) -> dict[str, object]:
        return {"text": "custom", "threadReply": False}

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.json() == {"text": "custom", "threadReply": False}


async def test_unhandled_event_returns_empty_200() -> None:
    app = _build_app(Dispatcher())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.content == b""


async def test_removed_from_space_returns_empty_200() -> None:
    router = Router()

    @router.removed_from_space()
    async def gone(event: RemovedFromSpaceEvent) -> None:
        return None

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    payload = {
        "type": "REMOVED_FROM_SPACE",
        "eventTime": "2026-08-13T12:35:00Z",
        "user": {"name": "users/123"},
        "space": {"name": "spaces/AAA"},
    }
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=payload)
    assert result.status_code == 200
    assert result.content == b""


async def test_verification_failure_returns_401() -> None:
    app = _build_app(_echo_dispatcher(), reject=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 401


async def test_malformed_json_returns_400() -> None:
    transport = httpx.ASGITransport(app=_build_app(_echo_dispatcher()))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", content=b"{not json")
    assert result.status_code == 400
    assert result.json() == {"error": "invalid_interaction_payload"}


async def test_handler_error_returns_500() -> None:
    router = Router()

    @router.message()
    async def boom(message: MessageEvent) -> None:
        raise RuntimeError("internal")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 500


async def test_double_response_returns_500() -> None:
    router = Router()

    @router.message()
    async def twice(message: MessageEvent, response: InteractionResponse) -> None:
        response.respond("one")
        response.respond("two")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 500


async def test_nan_payload_returns_500() -> None:
    router = Router()

    @router.message()
    async def nan(message: MessageEvent) -> dict[str, object]:
        return {"n": float("nan")}

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    transport = httpx.ASGITransport(app=_build_app(dispatcher))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 500


async def test_unknown_future_event_returns_empty_200() -> None:
    app = _build_app(Dispatcher())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post(
            "/", json={"type": "SOME_FUTURE_GOOGLE_EVENT", "extra": "data"}
        )
    assert result.status_code == 200
    assert result.content == b""


async def test_untyped_payload_returns_400() -> None:
    app = _build_app(_echo_dispatcher())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json={"foo": 1})
    assert result.status_code == 400
    assert result.json() == {"error": "invalid_interaction_payload"}


async def test_verification_receives_empty_body_snapshot() -> None:
    # Pins the verify-before-body order: the verifier must see the header-only
    # snapshot (body == b""), so unauthenticated clients get no body-read.
    seen: list[bytes] = []

    class RecordingVerifier:
        def verify(self, request: IncomingRequest) -> None:
            seen.append(request.body)
            raise VerificationError("rejected")

    app = FastAPI()
    app.include_router(create_chat_router(_echo_dispatcher(), RecordingVerifier()))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", content=b'{"type": "MESSAGE"}')
    assert result.status_code == 401
    assert seen == [b""]


async def test_works_under_plain_starlette() -> None:
    chat_router = create_chat_router(_echo_dispatcher(), MockVerifier())
    app = Starlette(routes=chat_router.routes)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert result.json() == {"text": "ping"}


async def test_handler_receives_capabilities_from_context() -> None:
    """The integration injects the NONE-mode capability set by DI name."""
    router = Router()
    seen: list[object] = []

    @router.message()
    async def echo(message: MessageEvent, capabilities: ResponseCapabilities) -> str:
        seen.append(capabilities)
        return message.text

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, MockVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert len(seen) == 1
    assert ResponseCapability.SYNC_RESPONSE in seen[0]  # type: ignore[operator]


async def test_verification_runs_off_the_event_loop() -> None:
    """The synchronous verifier (google-auth cert fetch) runs in a worker
    thread, never on the event loop."""
    import threading

    main_thread = threading.get_ident()
    seen: list[int] = []

    class _ThreadRecordingVerifier:
        def verify(self, request: object) -> None:
            seen.append(threading.get_ident())

    router = Router()

    @router.message()
    async def echo(message: MessageEvent) -> str:
        return message.text

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app = FastAPI()
    app.include_router(create_chat_router(dispatcher, _ThreadRecordingVerifier()))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post("/", json=_message_payload("ping"))
    assert result.status_code == 200
    assert seen and seen[0] != main_thread
