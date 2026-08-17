# ADR-010: Rename gchatogram to Chattice

- Status: Accepted
- Date: 2026-08-15

## Context

The project was developed under the working name `gchatogram` (Phases
0–14). Before the public beta the project needs an independent product
identity that does not read as a derivative of Google or Telegram naming.

## Decision

The project is renamed to **Chattice**:

- Python distribution and import namespace: `chattice`
- No `import gchatogram` compatibility alias — the project is still
  pre-public-beta, so a clean rename costs less than permanent alias debt
- Historic `gchatogram` references remain only where they explain project
  history (`.agent/plans/`, dated audits/reviews, research snapshots)

## Consequences

- Chattice is not official Google software and is not endorsed by Google.
- aiogram inspired architectural/DX ideas; Chattice does not copy
  Telegram semantics blindly.
- Google Chat remains the platform source of truth.
- Repo-wide rename touches: package sources, tests, examples, packaging,
  docs, CI, agent docs, and release metadata; a full gate cycle plus a
  clean-wheel `import chattice` check gates the rename.
