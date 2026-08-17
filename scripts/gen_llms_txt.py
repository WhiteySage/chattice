"""Generate llms.txt + llms-full.txt from the MkDocs documentation.

Usage: uv run python scripts/gen_llms_txt.py

The nav in mkdocs.yml is the single source of truth; these files are
GENERATED, never hand-maintained. `llms.txt` is a compact index (H1,
summary, file lists per the llmstxt.org convention); `llms-full.txt`
concatenates every public docs page with its title.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"


def nav_pages() -> list[tuple[str, str]]:
    """Return [(title, relative-path)] from mkdocs.yml nav in order."""
    raw = (ROOT / "mkdocs.yml").read_text()
    pattern = re.compile(r"^\s+-\s+([^:]+):\s+(\S+\.md)\s*$", re.M)
    return [(title.strip(), path) for title, path in pattern.findall(raw)]


def strip_md(path: str) -> str:
    return path[:-3] if path.endswith(".md") else path


def main() -> None:
    pages = nav_pages()
    index_lines = [
        "# Chattice",
        "",
        "> Async, typed event framework for Google Chat apps — aiogram-quality",
        "> DX, Google-native semantics. Public beta documentation.",
        "",
    ]
    full_parts = [
        "# Chattice — full documentation\n",
        "> Public beta. Google Chat-native Python framework with",
        "> aiogram-quality DX.\n",
    ]
    for title, path in pages:
        index_lines.append(f"- [{title}]({strip_md(path)}): {title}")
        file = DOCS / path
        if not file.exists():
            print(f"WARN missing {path}")
            continue
        body = file.read_text()
        # strip the page's own H1 so the full dump keeps the section title
        body = re.sub(r"^# .+\n", "", body, count=1).strip()
        full_parts.append(f"## {title}\n\n{body}\n")
    index_text = "\n".join(index_lines) + "\n"
    # docs/llms.txt is copied by MkDocs into site/ (Pages root);
    # the repo-root copy serves GitHub browsing agents directly.
    (DOCS / "llms.txt").write_text(index_text)
    (ROOT / "llms.txt").write_text(index_text)
    print(f"llms.txt: {len(pages)} pages -> docs/llms.txt + repo root")


if __name__ == "__main__":
    main()
