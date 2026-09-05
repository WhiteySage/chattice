"""Credentials provider contract."""

from __future__ import annotations

from google.auth.credentials import AnonymousCredentials

from chattice.client import CredentialsProvider


def test_callable_protocol_accepts_provider() -> None:
    credentials = AnonymousCredentials()  # type: ignore[no-untyped-call]

    class EnvProvider:
        def __call__(self) -> AnonymousCredentials:
            return credentials

    provider: CredentialsProvider = EnvProvider()
    assert provider() is credentials
