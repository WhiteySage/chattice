"""Credential providers for the outgoing Chat API modes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials

CHAT_BOT_SCOPE = "https://www.googleapis.com/auth/chat.bot"


class AuthMode(Enum):
    """The outgoing authentication identity class."""

    APP = "app"
    USER = "user"
    NONE = "none"


class CredentialsProvider(Protocol):
    """Callable returning Google credentials valid at call time."""

    def __call__(self) -> Credentials:
        """Return credentials valid at call time."""
        ...


def _service_account_file(path: str, scopes: list[str]) -> Credentials:
    """Load service-account credentials from a JSON file."""
    loader = service_account.Credentials.from_service_account_file
    creds = loader(path, scopes=scopes)  # type: ignore[no-untyped-call]
    return creds  # type: ignore[no-any-return]


def _service_account_info(info: Mapping[str, Any], scopes: list[str]) -> Credentials:
    """Load service-account credentials from an info mapping."""
    loader = service_account.Credentials.from_service_account_info
    creds = loader(info, scopes=scopes)  # type: ignore[no-untyped-call]
    return creds  # type: ignore[no-any-return]


def _user_credentials_info(info: Mapping[str, Any]) -> Credentials:
    """Load authorized-user credentials from a token-info mapping."""
    loader = UserCredentials.from_authorized_user_info
    creds = loader(dict(info))  # type: ignore[no-untyped-call]
    return creds  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class ServiceAccountCredentialsProvider:
    """App-auth provider: lazy service-account credentials.

    The JSON file/info is not read at construction — only when the
    provider is called (each call re-reads; the Bot calls it once).
    """

    credentials: Credentials | None = None
    file_path: str | None = None
    info: Mapping[str, Any] | None = None
    scopes: tuple[str, ...] = (CHAT_BOT_SCOPE,)

    @classmethod
    def from_service_account_file(
        cls, path: str | Path, scopes: list[str] | None = None
    ) -> ServiceAccountCredentialsProvider:
        """Build from a service-account JSON file path (lazily read)."""
        return cls(
            file_path=str(path),
            scopes=tuple(scopes) if scopes is not None else (CHAT_BOT_SCOPE,),
        )

    @classmethod
    def from_service_account_info(
        cls, info: Mapping[str, Any], scopes: list[str] | None = None
    ) -> ServiceAccountCredentialsProvider:
        """Build from an in-memory service-account info mapping."""
        return cls(
            info=dict(info),
            scopes=tuple(scopes) if scopes is not None else (CHAT_BOT_SCOPE,),
        )

    def __call__(self) -> Credentials:
        if self.credentials is not None:
            return self.credentials
        if self.file_path is not None:
            return _service_account_file(self.file_path, list(self.scopes))
        if self.info is not None:
            return _service_account_info(self.info, list(self.scopes))
        raise ValueError("ServiceAccountCredentialsProvider has no credentials source")


@dataclass(frozen=True, slots=True)
class UserCredentialsProvider:
    """User-auth provider: authorized-user credentials with lazy refresh.

    Token storage and OAuth code acquisition belong to the application.
    The refresh happens synchronously at call time (once, at lazy client
    creation in Bot); subsequent refreshes are handled inside the SDK.
    """

    credentials: Credentials | Mapping[str, Any]
    refresh_before_call: bool = True

    def __call__(self) -> Credentials:
        credentials = self._credentials()
        if (
            self.refresh_before_call
            and credentials.expired
            and hasattr(credentials, "refresh")
        ):
            credentials.refresh(Request())  # type: ignore[no-untyped-call]
        return credentials

    def _credentials(self) -> Credentials:
        if isinstance(self.credentials, Mapping):
            return _user_credentials_info(self.credentials)
        return self.credentials


__all__ = [
    "CHAT_BOT_SCOPE",
    "AuthMode",
    "CredentialsProvider",
    "ServiceAccountCredentialsProvider",
    "UserCredentialsProvider",
]
