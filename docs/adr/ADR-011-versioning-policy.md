# ADR-011: Versioning policy

- Status: Accepted

## Context

Users need predictable package versions and clear upgrade guidance while the
public API matures.

## Decision

1. The first public release is `0.1.2`.
2. Releases follow Semantic Versioning.
3. Before 1.0, incompatible public API changes require a minor-version bump
   and documented upgrade notes.
4. Patch releases remain backward compatible within the current minor line.
5. Publishing to PyPI or TestPyPI requires explicit maintainer authorization.

## Consequences

- `pyproject.toml` is the authoritative package version.
- Runtime metadata, documentation, tags, and release artifacts must use the
  same version.
- Every published change is recorded in `CHANGELOG.md`.
