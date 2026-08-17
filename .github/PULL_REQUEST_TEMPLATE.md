## What

One-line summary of the change.

## Why

Which Google-native semantic or framework contract this improves.

## Checks

- [ ] tests: `uv run pytest -q`
- [ ] typing/lint: `uv run mypy src tests && uv run ruff check . && uv run ruff format --check .`
- [ ] docs: `uv run mkdocs build --strict`
- [ ] package: `bash scripts/verify_package.sh`
- [ ] public API unchanged (additive only) or explicitly justified
- [ ] no credentials, internal material, or business entities added
