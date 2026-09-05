"""Backwards-compatible provider re-export and the experimental namespace."""

from __future__ import annotations

import importlib
import pathlib

from chattice.auth import CredentialsProvider as CanonicalProvider
from chattice.client.credentials import CredentialsProvider


def test_credentials_provider_reexport() -> None:
    assert CredentialsProvider is CanonicalProvider


def test_experimental_namespace_imports_standalone() -> None:
    module = importlib.import_module("chattice.experimental")
    assert module.__doc__ and "preview" in module.__doc__.lower()


def test_core_never_imports_experimental() -> None:
    src = pathlib.Path("src")
    offenders: list[str] = []
    for path in src.rglob("*.py"):
        if "experimental" in path.parts:
            continue
        text = path.read_text()
        if "chattice.experimental" in text:
            offenders.append(str(path))
    assert offenders == []
