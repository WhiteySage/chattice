"""Explicit-identity membership and Space listing resource operations."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from google.api_core import exceptions as api_core_exceptions
from google.apps.chat_v1.types import Membership, Space, User
from google.auth.credentials import AnonymousCredentials, Credentials

from chattice.auth import (
    CHAT_APP_MEMBERSHIPS_SCOPE,
    CHAT_BOT_SCOPE,
    AuthMode,
)
from chattice.capabilities import CapabilityNotSupported
from chattice.client import (
    Bot,
    ChatAlreadyExistsError,
    ChatAPIError,
    ChatNotFoundError,
    ChatPermissionDeniedError,
)
from chattice.events import SpaceRef, UserRef
from tests.client._fake_transport import FakeChatTransport


class _AppCredentials(AnonymousCredentials):
    def __init__(self, scopes: Iterable[str]) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.signer = object()
        self.scopes = tuple(scopes)


class _UserCredentials(AnonymousCredentials):
    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_token = "user-token"
        self.scopes = ("https://www.googleapis.com/auth/chat.memberships",)


class _CountingProvider:
    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self.calls = 0

    def __call__(self) -> Credentials:
        self.calls += 1
        return self.credentials


def _bot(
    transport: FakeChatTransport,
    *,
    scopes: Iterable[str] = (CHAT_BOT_SCOPE, CHAT_APP_MEMBERSHIPS_SCOPE),
) -> Bot:
    credentials = _AppCredentials(scopes)
    return Bot(
        credentials=credentials,
        auth_mode=AuthMode.APP,
        transport=transport,
    )


@pytest.mark.parametrize("user", ["user-123", "users/user-123"])
async def test_create_accepts_user_identifier_and_canonical_user(user: str) -> None:
    transport = FakeChatTransport()

    membership = await _bot(transport).app.memberships.create("AAA", user=user)

    request = transport.membership_creates[-1]
    assert request.parent == "spaces/AAA"
    assert request.membership.member.name == "users/user-123"
    assert membership.name == "spaces/AAA/members/user-123"
    assert membership.member.name == "users/user-123"


async def test_create_passes_explicit_user_type_through() -> None:
    transport = FakeChatTransport()

    await _bot(transport).app.memberships.create(
        "AAA", user="user-123", user_type=User.Type.HUMAN
    )

    assert transport.membership_creates[-1].membership.member.type_ == User.Type.HUMAN


async def test_create_accepts_typed_refs_and_canonical_space() -> None:
    transport = FakeChatTransport()

    await _bot(transport).app.memberships.create(
        SpaceRef(name="spaces/AAA"),
        user=UserRef(name="users/user-123"),
    )

    assert transport.membership_creates[-1].parent == "spaces/AAA"


async def test_create_rejects_missing_target_locally() -> None:
    transport = FakeChatTransport()

    with pytest.raises(ChatAPIError, match="user= or group="):
        await _bot(transport).app.memberships.create("AAA")
    assert transport.membership_creates == []


async def test_get_and_delete_by_membership_name() -> None:
    transport = FakeChatTransport()
    bot = _bot(transport)
    created = await bot.app.memberships.create("spaces/AAA", user="user-123")

    found = await bot.app.memberships.get("spaces/AAA/members/user-123")
    removed = await bot.app.memberships.delete("spaces/AAA/members/user-123")

    expected = "spaces/AAA/members/user-123"
    assert found == created
    assert removed == created
    assert transport.membership_gets[-1].name == expected
    assert transport.membership_deletes[-1].name == expected
    assert transport.membership_lists == []


@pytest.mark.parametrize(
    "name",
    ["AAA", "spaces/AAA/memberships/user-123", "", "spaces//members/user-123"],
)
async def test_get_rejects_malformed_membership_names(name: str) -> None:
    transport = FakeChatTransport()

    with pytest.raises(ChatAPIError):
        await _bot(transport).app.memberships.get(name)
    assert transport.membership_gets == []  # zero transport calls on invalid input


async def test_list_members_collects_all_pages_and_preserves_filter() -> None:
    transport = FakeChatTransport()
    transport.list_page_size = 1
    for user_id in ("user-a", "user-b", "user-c"):
        name = f"spaces/AAA/members/{user_id}"
        transport.memberships[name] = Membership(
            name=name,
            member=User(name=f"users/{user_id}", type_=User.Type.HUMAN),
        )

    pager = await _bot(transport).app.memberships.list(
        parent="AAA",
        filter='member.type = "HUMAN"',
    )
    memberships = await pager.collect()

    assert [item.member.name for item in memberships] == [
        "users/user-a",
        "users/user-b",
        "users/user-c",
    ]
    assert len(transport.membership_lists) == 3
    assert all(
        request.filter == 'member.type = "HUMAN"'
        for request in transport.membership_lists
    )


async def test_list_spaces_collects_all_pages_and_preserves_filter() -> None:
    transport = FakeChatTransport()
    transport.list_page_size = 1
    transport.spaces = {
        "spaces/A": Space(name="spaces/A", space_type=Space.SpaceType.SPACE),
        "spaces/B": Space(name="spaces/B", space_type=Space.SpaceType.SPACE),
        "spaces/C": Space(name="spaces/C", space_type=Space.SpaceType.SPACE),
    }

    pager = await _bot(transport).app.spaces.list(filter='spaceType = "SPACE"')
    spaces = await pager.collect()

    assert [space.name for space in spaces] == [
        "spaces/A",
        "spaces/B",
        "spaces/C",
    ]
    assert len(transport.space_lists) == 3
    assert all(
        request.filter == 'spaceType = "SPACE"' for request in transport.space_lists
    )


async def test_read_membership_and_space_list_accept_chat_bot_scope() -> None:
    transport = FakeChatTransport()
    membership_name = "spaces/AAA/members/user-123"
    transport.memberships[membership_name] = Membership(name=membership_name)
    transport.spaces["spaces/AAA"] = Space(name="spaces/AAA")
    bot = _bot(transport, scopes=(CHAT_BOT_SCOPE,))

    assert await bot.app.memberships.get("spaces/AAA/members/user-123")
    assert await (await bot.app.memberships.list(parent="AAA")).collect()
    assert await (await bot.app.spaces.list()).collect()

    with pytest.raises(CapabilityNotSupported, match="MEMBERSHIPS_CREATE"):
        await bot.app.memberships.create("AAA", user="users/other-user")
    with pytest.raises(CapabilityNotSupported, match="MEMBERSHIPS_DELETE"):
        await bot.app.memberships.delete("spaces/AAA/members/user-123")


async def test_membership_scope_does_not_grant_space_list() -> None:
    transport = FakeChatTransport()
    bot = _bot(transport, scopes=(CHAT_APP_MEMBERSHIPS_SCOPE,))

    await bot.app.memberships.create("AAA", user="user-123")
    assert await bot.app.memberships.get("spaces/AAA/members/user-123")
    assert await (await bot.app.memberships.list(parent="AAA")).collect()
    await bot.app.memberships.delete("spaces/AAA/members/user-123")

    with pytest.raises(CapabilityNotSupported, match="SPACES_LIST"):
        await (await bot.app.spaces.list()).collect()


async def test_membership_mutation_never_resolves_user_identity() -> None:
    transport = FakeChatTransport()
    app_provider = _CountingProvider(
        _AppCredentials((CHAT_BOT_SCOPE, CHAT_APP_MEMBERSHIPS_SCOPE))
    )
    user_provider = _CountingProvider(_UserCredentials())
    bot = Bot(
        app_credentials_provider=app_provider,
        user_credentials_provider=user_provider,
        transport=transport,
    )

    await bot.app.memberships.create("AAA", user="user-123")
    await bot.app.memberships.delete("spaces/AAA/members/user-123")

    assert app_provider.calls == 1
    assert user_provider.calls == 0


async def test_user_only_and_missing_credentials_fail_before_transport() -> None:
    user_only = Bot(
        credentials=_UserCredentials(),
        auth_mode=AuthMode.USER,
        transport=FakeChatTransport(),
    )
    no_credentials = Bot(transport=FakeChatTransport())
    for bot, expected in (
        (user_only, "Requested APP identity but resolved credentials are USER"),
        (no_credentials, "APP identity has no credentials"),
    ):
        with pytest.raises(CapabilityNotSupported, match=expected):
            await bot.app.memberships.create("AAA", user="user-123")
        transport = bot._transport
        assert isinstance(transport, FakeChatTransport)
        assert transport.membership_creates == []


async def test_membership_google_error_uses_existing_wrapper() -> None:
    error = api_core_exceptions.PermissionDenied("admin approval required")  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(error=error)

    with pytest.raises(ChatPermissionDeniedError) as caught:
        await _bot(transport).app.memberships.create("AAA", user="user-123")

    assert caught.value.__cause__ is error


async def test_membership_conflict_exposes_typed_error() -> None:
    error = api_core_exceptions.AlreadyExists("membership already exists")  # type: ignore[no-untyped-call]
    transport = FakeChatTransport(error=error)

    with pytest.raises(ChatAlreadyExistsError) as caught:
        await _bot(transport).app.memberships.create("AAA", user="user-123")

    assert caught.value.__cause__ is error


@pytest.mark.parametrize("operation", ["get", "delete"])
async def test_missing_membership_is_not_silently_swallowed(operation: str) -> None:
    transport = FakeChatTransport()
    bot = _bot(transport)

    with pytest.raises(ChatNotFoundError) as caught:
        if operation == "get":
            await bot.app.memberships.get("spaces/AAA/members/missing-user")
        else:
            await bot.app.memberships.delete("spaces/AAA/members/missing-user")

    assert isinstance(caught.value.__cause__, api_core_exceptions.NotFound)


@pytest.mark.parametrize(
    ("space", "user"),
    [("users/AAA", "users/user-123"), ("AAA", "groups/example")],
)
async def test_invalid_membership_targets_fail_locally(space: str, user: str) -> None:
    transport = FakeChatTransport()

    with pytest.raises(ChatAPIError):
        await _bot(transport).app.memberships.create(space, user=user)

    assert transport.membership_creates == []
