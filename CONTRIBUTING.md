# Contributing to Chattice

Chattice is an async Python framework for Google Chat apps. Contributions
that are naturally additive are the most welcome:

- new Google UI support (widgets, cards)
- Google API wrappers behind the raw escape hatch pattern
- tests, examples, docs, bug fixes

## Workflow

1. Open an issue describing the problem or idea (no PR-first for
   architectural changes — see the RFC rule below).
2. Branch off `main`; implement with tests.
3. Run the full gate suite:

   ```bash
   uv sync --all-groups
   uv run pytest -q
   uv run mypy src tests
   uv run ruff check . && uv run ruff format --check .
   uv run mkdocs build --strict
   bash scripts/verify_package.sh
   ```

4. Open a PR. The description must state: the problem, public API
   impact, compatibility impact, tests/docs added, risk level, and
   whether core changed.

## Rules

- New examples must expose a `main()` executed from
  `tests/test_examples.py` (docs can never drift).
- Fixtures must be official payload shapes with provenance recorded in
  `tests/fixtures/google_chat/interactions/README.md`.
- Public API changes require the public-API rule (charter §7): typing,
  tests, docs, deliberate export, compatibility review.
- Architectural changes (Dispatcher/Router/FSM contracts, new workflow
  engines, package splits, breaking API) require a lightweight design
  proposal first: Problem · Current behavior · Proposed API · Why the
  current API is insufficient · Alternatives · Compatibility ·
  Migration · Maintenance cost · Simpler solutions rejected.

## License

MIT. By contributing you agree your contributions are licensed
under it. No CLA required.

## Upstream Google changes

Google updates the wire layer (`google-apps-chat`, `google-apps-card`)
and ships Developer Preview features continuously. The public beta
surface stays frozen, so every upstream change follows ONE protocol:

1. An update PR arrives from dependabot (weekly, `google-sdks` group)
   or from the weekly `upstream-check` workflow's `upstream` issue.
2. CI runs the full suite, mypy/ruff, and the golden fixtures.
3. Wire analysis of the SDK diff:
   - a new event FIELD → keep it lossless (`raw`), add a round-trip
     test; no public API change;
   - a new event TYPE → decide: typed support (adapter + capability)
     or explicit `UnknownEvent`; update the Google API mapping and the
     capabilities matrix;
   - a breaking change → P0 issue, a Chattice semver decision (rare).
4. Update fixtures (reviewed), docs (mapping/capabilities), and the
   compatibility revision.
5. Pre-release: run every example (the `examples/docs/from_zero.py`
   journey plus the bots/scenarios).

Principles: Google updates are additive INSIDE the adapters; the public
Chattice surface changes only by Chattice's own semver decision. The
lossless paths (`UnknownEvent`, `RawWidget`, `Bot.raw_client`) absorb
new Google types — a new type must never crash existing bots.

