"""Compare the reviewed registry with the Google discovery document.

Machine-checked facts: method existence and OAuth scopes. Semantic
constraints (identity selection, admin approval, preview status) remain
human-reviewed metadata and are never generated (ADR-012).

A fabricated method (or a fabricated scope) fails the check with a
non-zero exit — the registry never drifts from the official document
silently.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# Standalone script: runnable from anywhere without the project on
# PYTHONPATH (CI executes it with `uv run python scripts/...`).
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chattice.capabilities import REGISTRY


def collect_methods(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Collect every method id (dotted resource path) from a discovery doc."""

    def walk(
        resources: Mapping[str, Any], prefix: str
    ) -> Iterable[tuple[str, Mapping[str, Any]]]:
        for name, resource in resources.items():
            full = f"{prefix}{name}"
            for method_name, method in (resource.get("methods") or {}).items():
                yield f"{full}.{method_name}", method
            yield from walk(resource.get("resources") or {}, f"{full}.")

    methods: dict[str, Mapping[str, Any]] = {}
    for method_id, method in walk(document.get("resources") or {}, ""):
        methods[method_id] = method
    return methods


def registry_facts() -> dict[str, set[str]]:
    """Return {google_method: scopes} straight from the registry specs."""
    return {
        spec.google_method: {
            scope for path in spec.auth_paths for scope in path.any_scope
        }
        for spec in REGISTRY
    }


def compare_with_discovery(
    *,
    google_methods: Mapping[str, Mapping[str, Any]] | None = None,
    registry_methods: set[str] | None = None,
    registry_scopes: Mapping[str, set[str]] | None = None,
) -> dict[str, list[str]]:
    """Compare registry facts with the discovery document.

    Returns {"missing": [...], "scope_mismatches": [...]}; an empty
    result means the registry is consistent with the document.
    """
    facts = registry_facts()
    methods = registry_methods if registry_methods is not None else set(facts)
    scopes_by_method = registry_scopes if registry_scopes is not None else facts
    google = google_methods if google_methods is not None else {}
    missing = sorted(methods - set(google))
    scope_mismatches = sorted(
        method
        for method, scopes in scopes_by_method.items()
        if method in google and not scopes <= set(google[method].get("scopes", []))
    )
    return {"missing": missing, "scope_mismatches": scope_mismatches}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/verify_registry.py <discovery.json>")
        return 2
    with open(sys.argv[1], encoding="utf-8") as handle:
        discovery = json.load(handle)
    report = compare_with_discovery(google_methods=collect_methods(discovery))
    print(json.dumps(report, indent=2))
    return 1 if report["missing"] or report["scope_mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
