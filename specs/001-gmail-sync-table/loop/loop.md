# Loop Contract

## Purpose
1. Drive every automatable task in `specs/001-gmail-sync-table/tasks.md` (T001–T044, Phases 1–6) to completion, landing each user story (US1, US2, US3) as its own git commit.

## Done-criteria
| ID | Criterion (checkable) | How the checker verifies it | Status |
|----|-----------------------|-----------------------------|--------|
| D1 | Setup + Foundational (T001–T014) done: package skeleton, errors, config, models, normalize, store, fixtures, fakes | `uv sync` exits 0; `uv run pytest tests/unit/test_models.py tests/unit/test_normalize.py tests/unit/test_store.py` exits 0; T001–T014 checked in tasks.md | checker-pass |
| D2 | Foundation landed as one commit | `git log --oneline` shows one commit for Phases 1–2 (e.g. `chore: project setup and foundational modules`); `git show --stat` touches only Phase 1–2 files | checker-pass |
| D3 | US1 automatable tasks (T015–T024, T026–T033) done | `uv run pytest` exits 0 incl. `test_gmail_client`, `contract/test_mcp_tools`, `test_extractor`, `test_merge`, `integration/test_sync_first_run`, `test_render`, `test_cli`; tasks checked | pending |
| D4 | T025 extractor gate passed (manual, Ollama) | `tests/golden/RESULTS.md` has a row with model, accuracy ≥ 90%, 0 non-job leaks, date (SC-003); human signs off in debt.md | human-signed |
| D5 | US1 landed as exactly one commit | One `feat(us1): ...` commit containing all Phase 3 files; `uv run pytest` green at that commit | pending |
| D6 | US2 (T034–T037) done and landed as one `feat(us2): ...` commit | `uv run pytest tests/unit/test_merge.py tests/integration/test_sync_incremental.py tests/unit/test_render.py` exits 0 at that commit; second sync yields zero changes/badges (SC-004 test) | pending |
| D7 | US3 (T038–T040) done and landed as one `feat(us3): ...` commit | `uv run pytest tests/unit/test_cli.py tests/unit/test_render_perf.py` exits 0 at that commit; perf test asserts < 2 s for 500 rows (SC-002) | pending |
| D8 | Polish (T041–T043) done | `uv run ruff check . && uv run ruff format --check . && uv run pytest` exits 0; `grep -rn "google.genai\|import ollama" src/` empty; `grep -rn "modify\|send\|trash\|batchDelete" src/applytrail/gmail_client.py` empty; README.md exists | pending |
| D9 | T044 quickstart validation on real mailbox (manual) | `tests/golden/RESULTS.md` records Scenarios 1–6 + 3b timing ≤ 60 s (SC-001); human signs off | pending |

Statuses: pending → maker-ready → checker-pass | checker-fail → human-signed.

## Budget
- Max iterations: 50
- Iterations run: 10
- Isolation: worktree
- Per-iteration scope: one phase, or one test+implementation task pair, per iteration. Never span two user stories in one iteration.

## Roles
- Maker: produces work toward the criteria (/speckit.loop.run).
- Checker: independent, adversarial grader (/speckit.loop.check). MUST be a
  separate agent/session from the maker.

## Allowed tools / connectors
- Core Spec Kit workflow (file edits, shell).
- `uv` (sync, run pytest, run ruff), `git` (branch, add, commit; no push, no force).
- Serena MCP for symbol navigation/edits.
- NOT allowed: live Gmail API, live Ollama calls (except human-run gates D4/D9), `git push`, new dependencies beyond plan.md.

## Automation trigger
- Manual: `/speckit.loop.run` per iteration, `/speckit.loop.check` from a separate session after each story commit. No scheduler/CI wired.

## Commit policy
- Work on branch `001-gmail-sync-table`, never commit on `main`.
- Commit boundaries: (1) Phases 1–2 foundation, (2) US1 / Phase 3, (3) US2 / Phase 4, (4) US3 / Phase 5, (5) Polish / Phase 6.
- Each user story = exactly one commit, made only after its phase checkpoint is green (`uv run pytest` exits 0).
- Conventional Commits: `feat(us1): ...`, `feat(us2): ...`, `feat(us3): ...`.

## Guardrails
- Human sign-off required before done: true
- Comprehension debt tracked: true
- Open blocking debt blocks done: true
- Manual gates T025 (D4) and T044 (D9) require a human run; maker pauses and records debt, never fakes RESULTS.md.
- Do not start T028+ until D4 is human-signed (tasks.md T025).

## State
- Phase: maker-ready
- Last updated: 2026-10-14
