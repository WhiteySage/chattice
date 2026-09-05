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
import hashlib
import json
import tomllib
import uuid
from pathlib import Path

_ROOT = Path(__file__).parents[1]
_DEFAULT_OUT = _ROOT / "docs" / "release" / "sbom-chattice.spdx.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT, help="output SPDX JSON path"
    )
    parser.add_argument(
        "--check", action="store_true", help="verify the existing SPDX document"
    )
    args = parser.parse_args()

    lock_text = (_ROOT / "uv.lock").read_text()
    lock = tomllib.loads(lock_text)
    version = None
    for pkg in lock.get("package", []):
        if pkg.get("name") == "chattice":
            version = pkg.get("version")
            break
    if version is None:
        raise SystemExit("chattice not found in uv.lock — cannot generate SBOM")
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]
    if version != project["version"]:
        raise SystemExit("Project and lockfile versions differ; run uv lock first")

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

    revision = uuid.uuid5(
        uuid.NAMESPACE_URL, hashlib.sha256(lock_text.encode()).hexdigest()
    )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"chattice-{version}-sbom",
        "documentNamespace": (
            f"https://spdx.org/spdxdocs/chattice-{version}-{revision}"
        ),
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: chattice-sbom"],
        },
        "packages": packages,
        "relationships": relationships,
    }
    content = json.dumps(document, indent=2) + "\n"
    if args.check:
        if not args.out.exists() or args.out.read_text() != content:
            raise SystemExit("SBOM is out of date; run python scripts/gen_sbom.py")
        print(f"SBOM matches the lockfile (version {version})")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content)
    print(f"SBOM written: {args.out} ({len(packages)} packages, version {version})")


if __name__ == "__main__":
    main()
