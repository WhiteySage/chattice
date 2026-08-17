# ADR-011: Versioning policy (pre-1.0 development releases)

- Status: Accepted
- Date: 2026-08-15

## Context

Development phases 2–15 shipped internal versions 0.2.0 → 0.13.0 (one
minor per phase); 0.14.0 is the first public beta candidate. An earlier
roadmap draft mentioned a public beta `0.9.0`. The current development
version is `0.14.0`; the FIRST PUBLIC BETA ships as `0.14.0b1`
(pre-release suffix on the same sequence, no downgrade).

## Decision

1. **No semantic-version downgrade.** The next public beta continues the
   existing sequence: **0.14.0** is the first public beta candidate.
   References to a `0.9.0` beta in earlier drafts are superseded.
2. Every development phase continues to bump the minor version; `1.0.0`
   follows only after public API stability demonstrated with real users.
3. Pre-1.0 semver rules are NOT applied to minor bumps (documented in
   CHANGELOG header); semver applies from 1.0.0 onward.
4. No publishing (PyPI/TestPyPI) without explicit owner authorization.

## Consequences

- One authoritative release sequence; roadmap/docs references updated to
  `0.14.0` as the first public beta candidate.
- Internal unreleased versions remain plainly labeled as development
  releases until the beta is authorized.
