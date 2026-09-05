"""Base for identity-bound resource clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from chattice.auth import AuthMode
from chattice.capabilities.operations import Operation
from chattice.client.config import RequestConfig
from chattice.client.executor import OperationExecutor

if TYPE_CHECKING:
    from chattice.client.bot import Bot

__all__ = ["ResourceClient"]


def _effective_config(
    config: RequestConfig | None, timeout: float | None
) -> RequestConfig:
    """Per-call config override: ``config`` wins over the ``timeout`` shorthand."""
    if config is not None:
        return config
    return RequestConfig(timeout=timeout)


class ResourceClient:
    """Base class for one resource facade bound to one identity.

    Subclasses own ONLY input normalization, request building, and
    response normalization. Credential selection, preflight, client
    lifecycle, timeout/retry/metadata plumbing, and the exception policy
    all live in :class:`OperationExecutor`.
    """

    def __init__(self, bot: Bot, identity: AuthMode) -> None:
        self._bot = bot
        self._identity = identity
        self._executor: OperationExecutor[Any] = OperationExecutor(bot)

    @property
    def identity(self) -> AuthMode:
        return self._identity

    async def _preflight(self, operation: Operation) -> None:
        """Registry preflight for THIS identity, before any side work.

        Runs the executor's spec/preview/preflight chain with a no-op
        call — used when a resource must fail locally BEFORE expensive
        or irreversible work (e.g. media uploads).
        """

        async def _noop(client: object, cfg: RequestConfig) -> None:
            del client, cfg

        await self._executor.execute(
            operation,
            identity=self._identity,
            call=_noop,
        )
