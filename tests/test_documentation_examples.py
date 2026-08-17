"""Documentation examples are executable and all Python fences parse."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from pytest import MonkeyPatch

from examples.docs.from_zero import main

_USER_DOCS = (
    Path("docs/index.md"),
    Path("docs/stability.md"),
    Path("docs/getting-started"),
    Path("docs/concepts"),
    Path("docs/guides"),
    Path("docs/cookbook"),
    Path("docs/reference"),
    Path("docs/common-mistakes.md"),
    Path("docs/aiogram-comparison.md"),
)


async def test_from_zero_documentation_journey() -> None:
    await main()


def test_quickstart_app_builds(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CHATTICE_AUDIENCE", "https://chat.example.com/")
    module = importlib.import_module("examples.docs.quickstart_app")
    assert module.app is not None


def test_public_documentation_python_fences_parse() -> None:
    for root in _USER_DOCS:
        files = [root] if root.is_file() else sorted(root.glob("**/*.md"))
        for path in files:
            source = path.read_text(encoding="utf-8")
            blocks = source.split("```python")[1:]
            for index, remainder in enumerate(blocks, start=1):
                block, marker, _tail = remainder.partition("```")
                assert marker, f"unterminated Python fence in {path}"
                ast.parse(block, filename=f"{path}:python-block-{index}")
