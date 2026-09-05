# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""Reaction resource client: USER-only reaction operations (ADR-012)."""

from __future__ import annotations

from typing import cast

from google.apps.chat_v1.types.reaction import (
    Emoji,
    ListReactionsRequest,
    Reaction,
)

from chattice.capabilities.operations import Operation
from chattice.client.config import RequestConfig
from chattice.client.executor import OperationExecutor
from chattice.client.paging import Pager
from chattice.client.resources.base import ResourceClient, _effective_config

__all__ = ["Reactions"]


class Reactions(ResourceClient):
    """Curated reaction surface bound to one identity (ADR-012).

    USER-only: the registry has no APP auth path for reactions, so the
    APP root fails at preflight.
    """

    async def create(
        self,
        message: str,
        *,
        emoji: str,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Reaction:
        """React to ``message`` (canonical name) with a unicode ``emoji``."""
        effective = _effective_config(config, timeout)
        reaction = Reaction(emoji=Emoji(unicode=emoji))
        return cast(
            Reaction,
            await self._executor.execute(
                Operation.REACTIONS_CREATE,
                identity=self._identity,
                call=lambda client, cfg: client.create_reaction(
                    request={"parent": message, "reaction": reaction},
                    **OperationExecutor.gapic_kwargs(cfg),
                ),
                config=effective,
            ),
        )

    async def list(
        self,
        message: str,
        *,
        page_size: int | None = None,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Pager[Reaction]:
        """List reactions on ``message``, one page at a time."""
        effective = _effective_config(config, timeout)
        request = ListReactionsRequest(parent=message)
        if page_size is not None:
            request.page_size = page_size

        async def fetch() -> object:
            return await self._executor.execute(
                Operation.REACTIONS_LIST,
                identity=self._identity,
                call=lambda client, cfg: client.list_reactions(
                    request=request, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            )

        return Pager(fetch=fetch)

    async def delete(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> None:
        """Delete one reaction by canonical name."""
        effective = _effective_config(config, timeout)
        await self._executor.execute(
            Operation.REACTIONS_DELETE,
            identity=self._identity,
            call=lambda client, cfg: client.delete_reaction(
                name=name, **OperationExecutor.gapic_kwargs(cfg)
            ),
            config=effective,
        )
