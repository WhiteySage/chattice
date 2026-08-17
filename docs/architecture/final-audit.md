# Final audit — Phase 12 (2026-08-15)

Ten-point full-project audit, executed by the controller against
`chattice==0.12.0` on branch `feat/phase-12-release-hardening`. Each item
records the check, the evidence, and the verdict. The audit list comes from
the master-plan checklist in the Phase 12 ExecPlan
(`.agent/plans/phase-12-release-hardening.md`).

## 1. Fresh environment — PASS

`bash scripts/verify_package.sh` builds the sdist + wheel, creates a fresh
venv in `/tmp` (no `--system-site-packages`), installs
`chattice` from `dist/` via `pip --find-links`, and asserts the import
resolves inside the venv (`chattice.__file__.startswith(sys.prefix)`), so
the source tree can never leak in.

Evidence: `Successfully built dist/chattice-0.12.0.tar.gz` and
`dist/chattice-0.12.0-py3-none-any.whl`; `wheel smoke OK: 0.12.0` (import
assert + mini-scenario: parse → dispatch → `"handled"`,
`assert_message_sent("ping")`).

## 2. Full tests — PASS

`uv run pytest -q`:

```
385 passed, 3 skipped in 2.60s
```

The 3 skips are the live integration suite
(`tests/integration/live/test_smoke.py`), honest and gated on
`GCHATOGRAM_GOOGLE_CREDENTIALS`. Phase 11 baseline was 376 tests + 3 skips;
the +9 are the named example-bot mains (`test_<name>_bot`).

Coverage (branch): **93%** (`fail_under = 90` gate green), 47 files fully
covered.

## 3. Static analysis — PASS

- `uv run ruff check .` — `All checks passed!`
- `uv run ruff format --check .` — `265 files already formatted`
- `uv run mypy src tests` (strict) — `Success: no issues found in 163 source
  files`

## 4. Documentation — PASS

- `uv run mkdocs build --strict` — built clean (Home first, then Research /
  Architecture / ADRs, then aiogram comparison, then Public API).
- Broken-link sweep: 79 relative links across `docs/**/*.md` resolved against
  the filesystem — 0 broken. One regex false positive in
  `docs/superpowers/plans/2026-08-14-phase-4-bot-api-client.md`
  (`rpc(request, retry=..., timeout=..., metadata=...)` inside backticks) —
  not a link.

## 5. Packaging — PASS

Wheel `dist/chattice-0.12.0-py3-none-any.whl`:

- `chattice/testing/` ships in full (`assertions`, `event_factory`,
  `fake_transport`, `fsm`, `mock_bot`, `__init__`).
- `chattice/experimental/__init__.py` ships as a marker.
- METADATA declares `Provides-Extra: fastapi` (`fastapi<1,>=0.115`) and
  `Provides-Extra: redis` (`redis<7,>=5`).
- sdist contains `src/`, `tests/`, `docs/`, `examples/` plus the ExecPlans.

## 6. Public API — PASS

`docs/public-api.md` enumerates every deliberate export per package; the
audit (Task 4) found and removed accidental exports, and
`tests/test_dispatcher.py::test_public_api_exports_are_intentional` pins the
top-level `__all__`. The verification script (item 1) runs the smoke
scenario against the **installed wheel**, and every example bot's `main()`
executes in the suite against the real API — the installed package and the
examples import the same symbols.

## 7. Security — PASS

Grep of `src/` for `private_key|client_secret|api_key`: no hardcoded
secrets; credentials flow only through `CredentialsProvider` /
`google-auth` objects. `Authorization` appears only in
`transports/http/verifier.py` (incoming-token extraction and validation,
all `VerificationError` paths map to HTTP 401). The source-scan redaction
test (`tests/reliability/test_redaction.py`) covers secret leakage in logs.

## 8. Dead code — PASS

No unused compat aliases found. The single deliberate re-export is
`client/credentials.py` (canonical home `chattice.auth`), kept for
Phase 4 import compatibility and documented in its docstring. DI event
aliases (`event`/`message`/`action`/`dialog_submit`/`dialog_cancel` in
`dispatcher/dependency.py`) are feature behavior, not dead code.

## 9. Docs/API drift — PASS

README and `docs/index.md` quickstarts were run against the real API:

1. Parse → dispatch (`parse_interaction` → `feed_update`, `F.text ==
   "ping"`) — `result == "pong"` ✓.
2. FastAPI wiring (`create_chat_router(dispatcher,
   GoogleTokenVerifier(audience="..."))`) — app builds, 5 routes registered;
   signature matches `create_chat_router(dispatcher, verifier, *, path)`.
3. `Bot(credentials=...)` construction — lazy SDK client, no network at
   construction; `send_message(space, text=...)` signature matches.

## 10. Google API drift — PASS

Critical research facts re-checked against code (no new contradictions):

- 30-second sync deadline —
  `transports/http/adapter.py: SYNC_RESPONSE_DEADLINE = timedelta(seconds=30)`.
- Verification failure → HTTP 401 —
  `integrations/fastapi/router.py: return Response(status_code=401)`.
- `UPDATE_MESSAGE` is bot-only — documented in
  `capabilities/matrix.py` ("(UPDATE_MESSAGE is BOT-only)").
- Dialogs are interaction-only — `cards/dialog.py` docstring: "displayed to
  the user who triggered the interaction".
- App Home requires `RenderActions` navigation responses — research
  `docs/research/google-chat.md` (lines 218–221, 318–319).
- Pub/Sub push envelope: Chat JSON wrapped in base64 `message.data`, no
  synchronous response channel — `transports/pubsub.py`
  (`decode_message_data`, `PubSubEnvelopeError`).
- CloudEvents `specversion == "1.0"` enforced —
  `workspace_events/parser.py` (`REQUIRED_SPECVERSION`).

## Summary

All ten points pass against version 0.12.0 (pre-1.0 beta / release
candidate). Known honest limitations: live integration tests are skeletons
until real credentials are provided; not published to PyPI; pre-1.0 API may
change.
