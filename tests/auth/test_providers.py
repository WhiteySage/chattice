"""Credential providers."""

from __future__ import annotations

from pathlib import Path

import pytest
from google.auth.credentials import AnonymousCredentials

from chattice.auth import (
    CHAT_BOT_SCOPE,
    AuthMode,
    CredentialsProvider,
    DelegatedUserCredentialsProvider,
    ServiceAccountCredentialsProvider,
    UserCredentialsProvider,
)


class _FlaggedCredentials(AnonymousCredentials):
    """Authorized-user stand-in with refresh tracking."""

    def __init__(self, *, expired: bool) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self._expired = expired
        self.refreshed = 0
        self.refresh_token = "rt"

    @property
    def expired(self) -> bool:
        return self._expired

    def refresh(self, request: object) -> None:
        self.refreshed += 1
        self._expired = False


def test_chat_bot_scope_constant() -> None:
    assert CHAT_BOT_SCOPE == "https://www.googleapis.com/auth/chat.bot"


def test_auth_mode_values() -> None:
    assert {m.value for m in AuthMode} == {"app", "user", "none"}


def test_service_account_provider_is_callable_protocol() -> None:
    provider: CredentialsProvider = ServiceAccountCredentialsProvider(
        credentials=AnonymousCredentials()  # type: ignore[no-untyped-call]
    )
    assert provider() is not None


def test_service_account_provider_lazy_from_file(tmp_path: Path) -> None:
    # The file must NOT be read at construction: pass a missing path and only
    # the call fails.
    path = tmp_path / "missing.json"
    provider = ServiceAccountCredentialsProvider.from_service_account_file(str(path))
    with pytest.raises(FileNotFoundError):
        provider()


def test_user_provider_refreshes_expired() -> None:
    credentials = _FlaggedCredentials(expired=True)
    provider = UserCredentialsProvider(credentials)
    result = provider()
    assert result.refreshed == 1  # type: ignore[attr-defined]


def test_user_provider_does_not_refresh_valid() -> None:
    credentials = _FlaggedCredentials(expired=False)
    provider = UserCredentialsProvider(credentials)
    result = provider()
    assert result.refreshed == 0  # type: ignore[attr-defined]


class _DelegatingCredentials(AnonymousCredentials):
    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.delegated_to: str | None = None

    def with_subject(self, subject: str) -> object | None:
        self.delegated_to = subject
        return self


class _NonDelegatingCredentials(AnonymousCredentials):
    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]

    def with_subject(self, subject: str) -> object | None:
        del subject
        return None


def test_delegated_provider_calls_with_subject() -> None:
    source = _DelegatingCredentials()
    provider = DelegatedUserCredentialsProvider(
        provider=lambda: source,
        subject="chat-bot-user@company.com",
    )
    result = provider()
    assert result.delegated_to == "chat-bot-user@company.com"  # type: ignore[attr-defined]


def test_delegated_provider_rejects_unsupported_credentials() -> None:
    provider = DelegatedUserCredentialsProvider(
        provider=lambda: _NonDelegatingCredentials(),
        subject="chat-bot-user@company.com",
    )
    with pytest.raises(ValueError, match="Domain-Wide Delegation"):
        provider()
