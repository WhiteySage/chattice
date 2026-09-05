# ruff: noqa: ASYNC109 — timeout kwarg mirrors the gapic client call convention
"""Space resource client: explicit-identity space operations (ADR-012)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from google.apps.chat_v1.types import Space
from google.apps.chat_v1.types.membership import Membership
from google.apps.chat_v1.types.space import ListSpacesRequest
from google.apps.chat_v1.types.user import User as ProtoUser

from chattice.auth import AuthMode
from chattice.capabilities.operations import Operation
from chattice.client._names import _canonical_user
from chattice.client.config import RequestConfig
from chattice.client.errors import ChatAPIError, ChatNotFoundError
from chattice.client.executor import OperationExecutor
from chattice.client.paging import Pager
from chattice.client.resources.base import ResourceClient, _effective_config

if TYPE_CHECKING:
    from chattice.client.bot import Bot

__all__ = ["Spaces"]


class Spaces(ResourceClient):
    """Curated space surface bound to one identity (ADR-012).

    No implicit identity selection: the identity is chosen by which Bot
    namespace the caller used (``bot.app.spaces`` vs ``bot.user.spaces``).
    """

    def __init__(self, bot: Bot, identity: AuthMode, *, allow_setup: bool) -> None:
        super().__init__(bot, identity)
        self._allow_setup = allow_setup

    async def get(
        self,
        name: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Space:
        """Get one space by canonical ``spaces/{id}`` name."""
        effective = _effective_config(config, timeout)
        return cast(
            Space,
            await self._executor.execute(
                Operation.SPACES_GET,
                identity=self._identity,
                call=lambda client, cfg: client.get_space(
                    name=name, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def list(
        self,
        *,
        filter: str | None = None,
        page_size: int | None = None,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Pager[Space]:
        """List spaces the identity can see, one page at a time."""
        effective = _effective_config(config, timeout)
        request = self._list_request(filter, page_size)

        async def fetch() -> object:
            return await self._executor.execute(
                Operation.SPACES_LIST,
                identity=self._identity,
                call=lambda client, cfg: client.list_spaces(
                    request=request, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            )

        return Pager(fetch=fetch)

    @staticmethod
    def _list_request(filter: str | None, page_size: int | None) -> ListSpacesRequest:
        request = ListSpacesRequest()
        if page_size is not None:
            request.page_size = page_size
        if filter is not None:
            request.filter = filter
        return request

    async def find_direct_message(
        self,
        user: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Space:
        """Find the 1:1 direct-message space with ``user``.

        ``user`` is a bare user ID, an email, or a canonical
        ``users/{id}`` resource name. Returns the official Google
        ``Space``. Errors are surfaced through the curated ``Chat*Error``
        family — ``ChatPermissionDeniedError`` / ``ChatInvalidArgumentError``
        / ``ChatNotFoundError`` are never hidden.
        """
        name = _canonical_user(user, parameter="user")
        effective = _effective_config(config, timeout)
        return cast(
            Space,
            await self._executor.execute(
                Operation.SPACES_FIND_DIRECT_MESSAGE,
                identity=self._identity,
                call=lambda client, cfg: client.find_direct_message(
                    request={"name": name}, **OperationExecutor.gapic_kwargs(cfg)
                ),
                config=effective,
            ),
        )

    async def get_or_setup_direct_message(
        self,
        user: str,
        *,
        timeout: float | None = None,
        config: RequestConfig | None = None,
    ) -> Space:
        """Find the DM space, or create it via ``setUpSpace`` on 404.

        USER identity only: creating a DM on behalf of the app would
        silently change who is talking to whom. ``PermissionDenied`` /
        ``InvalidArgument`` are surfaced, never hidden.
        """
        if not self._allow_setup:
            raise ChatAPIError(
                "get_or_setup_direct_message requires the USER identity; "
                "use bot.user.spaces.get_or_setup_direct_message(...)"
            )
        name = _canonical_user(user, parameter="user")
        try:
            # find_direct_message preflights SPACES_FIND_DIRECT_MESSAGE.
            return await self.find_direct_message(user, timeout=timeout, config=config)
        except ChatNotFoundError:
            pass
        effective = _effective_config(config, timeout)
        space = Space(space_type=Space.SpaceType.DIRECT_MESSAGE)
        membership = Membership(member=ProtoUser(name=name, type_=ProtoUser.Type.HUMAN))
        return cast(
            Space,
            await self._executor.execute(
                Operation.SPACES_SETUP,
                identity=self._identity,
                call=lambda client, cfg: client.set_up_space(
                    request={"space": space, "memberships": [membership]},
                    **OperationExecutor.gapic_kwargs(cfg),
                ),
                config=effective,
            ),
        )
