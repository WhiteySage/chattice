"""Architecture invariants enforced mechanically (B7).

Machine-enforced dependency direction beats permanent prompt rules:
- core must not import AI, Redis, or FastAPI at module level;
- FastAPI lives only in the integrations layer;
- Redis lives only behind lazy imports in the fsm/idempotency storages;
- every public ``__all__`` symbol is importable (no dead exports).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).parents[1] / "src" / "chattice"

# Module-level (non-lazy) imports only; TYPE_CHECKING blocks are exempt.
_REDIS_ALLOWED = {
    "chattice.fsm.redis",  # the lazy-loaded RedisStorage module itself
}
_FASTAPI_ALLOWED = {
    "chattice.integrations.fastapi.router",  # the FastAPI integration itself
}


def _module_imports(path: Path) -> tuple[str, list[ast.stmt]]:
    module = path.read_text()
    tree = ast.parse(module)
    return module, list(tree.body)


def _top_level_import_roots(body: list[ast.stmt], source: str) -> set[str]:
    """Root module names imported at top level, ignoring TYPE_CHECKING.

    F12: only the TYPE_CHECKING conditional's BODY is exempt — the
    previous flag never reset, so every import after the first
    TYPE_CHECKING block in a module was silently ignored.
    """
    roots: set[str] = set()
    for node in body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            continue  # the whole conditional — only its body is type-only
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_type_checking_block_does_not_hide_later_imports() -> None:
    """F12 mutation guard: only the TYPE_CHECKING conditional's body is
    exempt — an import AFTER the block must still be detected (the old
    never-reset flag hid it)."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import redis\n"  # exempt: type-only
        "import fastapi\n"  # NOT exempt: runtime import after the block
    )
    tree = ast.parse(source)
    roots = _top_level_import_roots(list(tree.body), source)
    assert "fastapi" in roots
    assert "redis" not in roots


def test_core_never_imports_fastapi_redis_or_ai() -> None:
    violations: list[str] = []
    for path in _SRC.rglob("*.py"):
        module_name = "chattice." + str(path.relative_to(_SRC)).replace("/", ".")[:-3]
        body = _module_imports(path)[1]
        roots = _top_level_import_roots(body, "")
        if "fastapi" in roots and module_name not in _FASTAPI_ALLOWED:
            violations.append(f"{module_name}: imports fastapi")
        if "redis" in roots and module_name not in _REDIS_ALLOWED:
            violations.append(f"{module_name}: imports redis at top level")
        if "chattice" in roots and not module_name.startswith(
            "chattice.experimental.ai"
        ):
            # core must never import the experimental AI package; the
            # integration itself may import its own package.
            for node in body:
                if isinstance(node, (ast.Import, ast.ImportFrom)) and (
                    "chattice.experimental.ai" in ast.unparse(node)
                ):
                    violations.append(
                        f"{module_name}: imports chattice.experimental.ai"
                    )
    assert violations == [], "dependency-direction violations:\n" + "\n".join(
        violations
    )


def test_fastapi_imports_only_in_the_integration() -> None:
    for path in _Src_files():
        module_name = _module_name(path)
        if module_name in _FASTAPI_ALLOWED:
            continue
        body = _module_imports(path)[1]
        roots = _top_level_import_roots(body, "")
        assert "fastapi" not in roots, f"{module_name} imports fastapi"


def _modules_from_source_tree() -> list[str]:
    """F12: discover packages AND plain modules that declare __all__
    from the source tree — a new namespace can never be forgotten."""
    modules: list[str] = []
    for path in _SRC.rglob("*.py"):
        rel = path.relative_to(_SRC)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            name = "chattice" if len(parts) == 1 else "chattice." + ".".join(parts[:-1])
        else:
            if "__all__" not in path.read_text():
                continue  # internal helper without a public surface
            name = "chattice." + ".".join(parts)
        modules.append(name)
    return sorted(modules)


def test_every_public_export_is_importable() -> None:
    """Each package __all__ symbol resolves on import (no dead exports)."""
    import importlib

    for package in _modules_from_source_tree():
        module = importlib.import_module(package)
        exports = getattr(module, "__all__", None)
        if exports is None:
            continue
        for name in exports:
            assert hasattr(module, name), f"{package}.{name} is a dead export"


def test_export_check_discovers_every_namespace_with_all() -> None:
    """F12 mutation guard: the discovery covers namespaces that carry
    __all__ — a manual allowlist would have silently missed new ones."""
    modules = _modules_from_source_tree()
    for required in (
        "chattice",
        "chattice.experimental.ai",
        "chattice.capabilities",
        "chattice.cards",
        "chattice.client",
        "chattice.transports.pubsub",
        "chattice.workspace_events",
    ):
        assert required in modules, f"{required} missing from discovery"


def _Src_files() -> list[Path]:
    return list(_SRC.rglob("*.py"))


def _module_name(path: Path) -> str:
    return "chattice." + str(path.relative_to(_SRC)).replace("/", ".")[:-3]


def test_no_icloud_duplicate_artifacts() -> None:
    """macOS iCloud sync occasionally materializes 'name 2.ext' clones of
    tracked files. Detect them mechanically instead of relying on memory:
    any basename matching ' 2.<ext>' in the repo is a hygiene failure."""
    import re

    root = _SRC.parent.parent
    pattern = re.compile(r" 2\.(py|md|toml|yml|yaml|json|sh)$")
    offenders: list[str] = []
    for path in root.rglob("*"):
        if ".git" in path.parts or ".venv" in path.parts or "site" in path.parts:
            continue
        if path.is_file() and pattern.search(path.name):
            offenders.append(str(path))
    assert offenders == [], "duplicate artifacts detected:\n" + "\n".join(offenders)


def test_examples_import_only_public_api() -> None:
    """Public docs/examples must never import private modules — the docs are
    the dogfood surface."""
    import ast

    allowed_roots = {
        "chattice.actions",
        "chattice.experimental.ai",
        "chattice.adapters.google_chat",
        "chattice.auth",
        "chattice.capabilities",
        "chattice.cards",
        "chattice.client",
        "chattice.dispatcher",
        "chattice.events",
        "chattice.filters",
        "chattice.forms",
        "chattice.fsm",
        "chattice.idempotency",
        "chattice.integrations.fastapi",
        "chattice.middleware",
        "chattice.observability",
        "chattice.testing",
        "chattice.transports.http",
        "chattice.transports.pubsub",
        "chattice.workspace_events",
        "examples",
    }
    violations: list[str] = []
    examples_root = _SRC.parent.parent / "examples"
    for path in examples_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "chattice":
                    # F12: the root package itself is public — but it is
                    # NOT a prefix: chattice._private stays banned.
                    continue
                if node.module.startswith("chattice"):
                    if not any(
                        node.module == root or node.module.startswith(root + ".")
                        for root in allowed_roots
                    ):
                        violations.append(f"{path.name}: imports {node.module}")
    assert violations == [], "examples import non-public modules:\n" + "\n".join(
        violations
    )


def test_version_derives_from_package_metadata() -> None:
    """One version source: importlib.metadata (pyproject) must equal the
    runtime __version__ — no independent literals."""
    import importlib.metadata

    import chattice

    assert importlib.metadata.version("chattice") == chattice.__version__
