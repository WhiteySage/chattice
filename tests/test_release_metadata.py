"""The release dependency inventory must match the lockfile."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_sbom_matches_locked_dependencies() -> None:
    subprocess.run([sys.executable, "scripts/gen_sbom.py", "--check"], check=True)


def test_sbom_check_rejects_stale_package_without_overwriting(tmp_path: Path) -> None:
    document = json.loads(Path("docs/release/sbom-chattice.spdx.json").read_text())
    document["packages"][0]["versionInfo"] = "0.0.0"
    target = tmp_path / "sbom.json"
    content = json.dumps(document, indent=2) + "\n"
    target.write_text(content)

    result = subprocess.run(
        [sys.executable, "scripts/gen_sbom.py", "--check", "--out", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "out of date" in result.stderr
    assert target.read_text() == content
