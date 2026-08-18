# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""In-memory fake Chat API transport for tests (no network, no credentials).

Ships in :mod:`chattice.testing` (framework-internal testing toolkit).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from google.apps.chat_v1.services.chat_service import transports
from google.apps.chat_v1.types.attachment import (
    Attachment,
    GetAttachmentRequest,
)
from google.apps.chat_v1.types.message import (
    CreateMessageRequest,
    DeleteMessageRequest,
    GetMessageRequest,
    Message,
    UpdateMessageRequest,
)
from google.apps.chat_v1.types.space import GetSpaceRequest, Space


class FakeChatTransport(transports.ChatServiceTransport):
    """Subclass of the SDK transport; only the methods Bot uses are real.

    Mirrors the gapic transport contract: the client invokes
    ``self._transport._wrapped_methods[method](request, retry=..., timeout=...,
    metadata=...)`` and reads ``self._transport.host``.
    """

    _matching_host = "chat.googleapis.com"

    def __init__(
        self, error: Exception | None = None, *, credentials: object = None
    ) -> None:
        # The gapic client requires a transport instance to carry credentials
        # itself ("When providing a transport instance, provide its credentials
        # directly") — we accept and store them without using them.
        self.credentials = credentials
        self.error = error
        self.messages: dict[str, Message] = {}
        self.spaces: dict[str, Space] = {}
        self.attachments: dict[str, Attachment] = {}
        self.requests: list[CreateMessageRequest] = []
        self.updates: list[UpdateMessageRequest] = []
        self.timeouts: list[object] = []
        self.delay: float = 0.0
        self.calls: list[int] = []
        # Keys MUST be bound methods: the client looks up
        # self._transport._wrapped_methods[self._transport.create_message].
        self._wrapped_methods = {
            self.create_message: self._wrap(self.create_message),
            self.get_message: self._wrap(self.get_message),
            self.update_message: self._wrap(self.update_message),
            self.delete_message: self._wrap(self.delete_message),
            self.get_space: self._wrap(self.get_space),
            self.get_attachment: self._wrap(self.get_attachment),
        }

    @property
    def host(self) -> str:
        return "fake-chat"

    def _wrap(
        self, method: Callable[..., Awaitable[object]]
    ) -> Callable[..., Awaitable[object]]:
        async def wrapped(
            request: object,
            *,
            retry: object = None,
            timeout: object = None,
            metadata: object = (),
        ) -> object:
            return await method(
                request, retry=retry, timeout=timeout, metadata=metadata
            )

        return wrapped

    def _check_error(self) -> None:
        if self.error is not None:
            raise self.error

    async def create_message(
        self,
        request: CreateMessageRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> Message:
        # Record the attempt on entry so a call that fails (error configured)
        # is still counted: the framework made exactly one transport call.
        self.calls.append(1)
        self.timeouts.append(timeout)
        self._check_error()
        if self.delay:
            await asyncio.sleep(self.delay)
        self.requests.append(request)
        if request.message_id:
            name = f"{request.parent}/messages/{request.message_id}"
        else:
            name = f"{request.parent}/messages/fake-{len(self.requests)}"
        message = Message(name=name, text=request.message.text)
        if request.message.thread.name:
            message.thread.name = request.message.thread.name
        self.messages[name] = message
        return message

    async def get_message(
        self,
        request: GetMessageRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> Message:
        self._check_error()
        message = self.messages.get(request.name)
        if message is None:
            from google.api_core import exceptions

            raise exceptions.NotFound(f"message not found: {request.name}")  # type: ignore[no-untyped-call]
        return message

    async def update_message(
        self,
        request: UpdateMessageRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> Message:
        self._check_error()
        self.updates.append(request)
        current = self.messages.get(request.message.name)
        if current is None:
            from google.api_core import exceptions

            raise exceptions.NotFound(f"message not found: {request.message.name}")  # type: ignore[no-untyped-call]
        updated = Message(name=current.name, text=request.message.text)
        self.messages[current.name] = updated
        return updated

    async def delete_message(
        self,
        request: DeleteMessageRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> None:
        self._check_error()
        self.messages.pop(request.name, None)

    async def get_space(
        self,
        request: GetSpaceRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> Space:
        self._check_error()
        space = self.spaces.get(request.name)
        if space is None:
            from google.api_core import exceptions

            raise exceptions.NotFound(f"space not found: {request.name}")  # type: ignore[no-untyped-call]
        return space

    async def get_attachment(
        self,
        request: GetAttachmentRequest,
        *,
        retry: object = None,
        timeout: object = None,
        metadata: object = (),
    ) -> Attachment:
        self._check_error()
        attachment = self.attachments.get(request.name)
        if attachment is None:
            from google.api_core import exceptions

            raise exceptions.NotFound(f"attachment not found: {request.name}")  # type: ignore[no-untyped-call]
        return attachment
