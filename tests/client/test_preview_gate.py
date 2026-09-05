"""Preview gating: registry marks preview surface, Bot opts in explicitly."""

from __future__ import annotations

import pytest

from chattice.auth import AuthMode
from chattice.capabilities import CapabilityNotSupported, Operation
from chattice.capabilities.operations import (
    AuthPath,
    OperationSpec,
    scopes,
)
from chattice.capabilities.registry import OperationRegistry
from chattice.client import Bot
from chattice.client.config import RequestConfig
from chattice.client.executor import OperationExecutor
from chattice.testing import FakeChatTransport
from tests.client.test_identity_clients import _creds

_PREVIEW_SPEC = OperationSpec(
    operation=Operation.SPACES_SEARCH,
    google_method="spaces.search",
    auth_paths=(AuthPath(AuthMode.APP, scopes("chat.bot")),),
    preview=True,
    description="Preview search operation.",
)
_PREVIEW_REGISTRY = OperationRegistry([_PREVIEW_SPEC])


def _bot(*, enable_preview: bool) -> Bot:
    return Bot(
        credentials=_creds(),
        transport=FakeChatTransport(credentials=_creds()),
        enable_preview=enable_preview,
    )


async def test_preview_disabled_rejects_with_clear_error() -> None:
    bot = _bot(enable_preview=False)
    executor: OperationExecutor[object] = OperationExecutor(
        bot, registry=_PREVIEW_REGISTRY
    )

    async def call(client: object, config: RequestConfig) -> object:
        raise AssertionError("must not be called")

    with pytest.raises(CapabilityNotSupported, match="enable_preview"):
        await executor.execute(
            Operation.SPACES_SEARCH, identity=AuthMode.APP, call=call
        )


async def test_preview_enabled_allows_operation() -> None:
    bot = _bot(enable_preview=True)
    executor: OperationExecutor[object] = OperationExecutor(
        bot, registry=_PREVIEW_REGISTRY
    )

    async def call(client: object, config: RequestConfig) -> object:
        return "ran"

    assert (
        await executor.execute(
            Operation.SPACES_SEARCH, identity=AuthMode.APP, call=call
        )
        == "ran"
    )


async def test_stable_operation_is_allowed_without_opt_in() -> None:
    bot = _bot(enable_preview=False)
    executor: OperationExecutor[object] = OperationExecutor(bot)

    async def call(client: object, config: RequestConfig) -> object:
        return "stable"

    # MESSAGES_GET is a stable (preview=False) operation in the default
    # registry — no opt-in required.
    assert (
        await executor.execute(Operation.MESSAGES_GET, identity=AuthMode.APP, call=call)
        == "stable"
    )
