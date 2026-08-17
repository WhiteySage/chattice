"""Generate an SPDX 2.3 JSON SBOM from uv.lock.

Usage: uv run python scripts/gen_sbom.py [--out PATH]

The lockfile is the single source of truth for the resolved dependency
set; the output is a release artifact committed under docs/release/.
License fields are taken from the lock where present, otherwise
NOASSERTION (see THIRD_PARTY_NOTICES.md for the direct-dependency
license inventory).
"""

from __future__ import annotations

import argparse
import json
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_DEFAULT_OUT = _ROOT / "docs" / "release" / "sbom-chattice.spdx.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT, help="output SPDX JSON path"
    )
    args = parser.parse_args()

    lock = tomllib.loads((_ROOT / "uv.lock").read_text())
    version = "0.0.0"
    for pkg in lock.get("package", []):
        if pkg.get("name") == "chattice":
            version = pkg.get("version", version)

    packages = []
    relationships = []
    for pkg in sorted(lock.get("package", []), key=lambda p: (p["name"], p["version"])):
        name = pkg["name"]
        pkg_version = pkg.get("version", "0.0.0")
        spdx_id = f"SPDXRef-Package-{name}"
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": name,
                "versionInfo": pkg_version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": pkg.get("license") or "NOASSERTION",
                "licenseDeclared": pkg.get("license") or "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relatedSpdxElement": spdx_id,
                "relationshipType": "DESCRIBES",
            }
        )

    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"chattice-{version}-sbom",
        "documentNamespace": (
            f"https://spdx.org/spdxdocs/chattice-{version}-{uuid.uuid4()}"
        ),
        "creationInfo": {
            "created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: chattice-scripts/gen_sbom.py"],
        },
        "packages": packages,
        "relationships": relationships,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=2) + "\n")
    print(f"SBOM written: {args.out} ({len(packages)} packages, version {version})")


if __name__ == "__main__":
    main()
