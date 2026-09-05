# ADR-010: Project identity

- Status: Accepted

## Context

The package needs a concise identity that communicates its Google Chat focus
without implying that it is official Google software.

## Decision

- Project name: **Chattice**.
- Python distribution and import namespace: `chattice`.
- Google Chat remains the platform source of truth.
- Documentation clearly states that Chattice is an independent project and is
  not endorsed by Google.

## Consequences

Package metadata, documentation, examples, CI, and release artifacts use the
same project name and import namespace.
