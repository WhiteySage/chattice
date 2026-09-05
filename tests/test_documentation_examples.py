"""Documentation examples are executable and all Python fences parse."""

from __future__ import annotations

import ast
import asyncio
import importlib
from pathlib import Path

from pytest import MonkeyPatch

from examples.docs.from_zero import main

_USER_DOCS = (
    Path("README.md"),
    Path("CONTRIBUTING.md"),
    Path("PUBLIC_API.md"),
    Path("examples/README.md"),
    Path("docs"),
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
                tree = ast.parse(block, filename=f"{path}:python-block-{index}")
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.ImportFrom)
                        and node.module
                        and node.module.startswith("chattice")
                    ):
                        module = importlib.import_module(node.module)
                        for alias in node.names:
                            assert hasattr(module, alias.name), (
                                f"{path}: {node.module}.{alias.name} is not importable"
                            )


async def test_readme_ping_routes() -> None:
    from chattice import Dispatcher
    from chattice.events import MessageEvent

    source = await asyncio.to_thread(Path("README.md").read_text)
    block = source.split("```python", 1)[1].split("```", 1)[0]
    namespace: dict[str, object] = {}
    exec(compile(block, "README.md", "exec"), namespace)
    dispatcher = namespace["dispatcher"]
    assert isinstance(dispatcher, Dispatcher)
    assert await dispatcher.feed_update(MessageEvent(text="ping")) == "pong"


def test_documentation_version_matches_package() -> None:
    from chattice import __version__

    assert (
        f"is `{__version__}`"
        in Path("docs/getting-started/installation.md").read_text()
    )
    assert (
        f"| Chattice | {__version__} |"
        in Path("docs/reference/compatibility.md").read_text()
    )
    assert (
        f"snapshot for Chattice {__version__}."
        in Path("docs/public-api.md").read_text()
    )


def test_documented_card_assertions_pass() -> None:
    source = Path("docs/architecture/testing.md").read_text()
    section = source.split("## Card assertions", 1)[1]
    block = section.split("```python", 1)[1].split("```", 1)[0]
    exec(compile(block, "docs/architecture/testing.md", "exec"), {})
