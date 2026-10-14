# Loop Contract

## Purpose
1. Drive every automatable task in `specs/001-gmail-sync-table/tasks.md` (T001–T044, Phases 1–6) to completion, landing each user story (US1, US2, US3) as its own git commit.
2. (Added 2026-10-14) Drive Phase 7 of `tasks.md` (T045–T054) to completion: migrate the MCP server and client from the `mcp` 2.x SDK (`MCPServer`, `mcp.Client`) to `fastmcp` 4.x with the wire contract unchanged (plan.md "FastMCP migration scope", research.md R1), landed as one commit.

## Done-criteria
| ID | Criterion (checkable) | How the checker verifies it | Status |
|----|-----------------------|-----------------------------|--------|
| D1 | Setup + Foundational (T001–T014) done: package skeleton, errors, config, models, normalize, store, fixtures, fakes | `uv sync` exits 0; `uv run pytest tests/unit/test_models.py tests/unit/test_normalize.py tests/unit/test_store.py` exits 0; T001–T014 checked in tasks.md | checker-pass |
| D2 | Foundation landed as one commit | `git log --oneline` shows one commit for Phases 1–2 (e.g. `chore: project setup and foundational modules`); `git show --stat` touches only Phase 1–2 files | checker-pass |
| D3 | US1 automatable tasks (T015–T024, T026–T033) done | `uv run pytest` exits 0 incl. `test_gmail_client`, `contract/test_mcp_tools`, `test_extractor`, `test_merge`, `integration/test_sync_first_run`, `test_render`, `test_cli`; tasks checked | checker-pass |
| D4 | T025 extractor gate passed (manual, Ollama) | `tests/golden/RESULTS.md` has a row with model, accuracy ≥ 90%, 0 non-job leaks, date (SC-003); human signs off in debt.md | human-signed |
| D5 | US1 landed as exactly one commit | One `feat(us1): ...` commit containing all Phase 3 files; `uv run pytest` green at that commit | checker-pass |
| D6 | US2 (T034–T037) done and landed as one `feat(us2): ...` commit | `uv run pytest tests/unit/test_merge.py tests/integration/test_sync_incremental.py tests/unit/test_render.py` exits 0 at that commit; second sync yields zero changes/badges (SC-004 test) | checker-pass |
| D7 | US3 (T038–T040) done and landed as one `feat(us3): ...` commit | `uv run pytest tests/unit/test_cli.py tests/unit/test_render_perf.py` exits 0 at that commit; perf test asserts < 2 s for 500 rows (SC-002) | checker-pass |
| D8 | Polish (T041–T043) done | `uv run ruff check . && uv run ruff format --check . && uv run pytest` exits 0; `grep -rn "google.genai\|import ollama" src/` empty; `grep -rnw "modify\|send\|trash\|batchDelete" src/applytrail/gmail_client.py` empty (whole words; human ruling 2026-10-14); README.md exists | checker-pass |
| D9 | T044 quickstart validation on real mailbox (manual) | `tests/golden/RESULTS.md` records Scenarios 1–6; Scenario 3b (timing ≤ 60 s, SC-001) excluded by human ruling 2026-10-14, see DEBT-002; human signs off | checker-pass |
| D10 | Goal 2: T045 dependency swapped | `pyproject.toml` lists `fastmcp>=4.1,<5` and no direct `mcp` dependency; `uv sync` exits 0; `uv run python -c "import importlib.metadata as m; print(m.version('fastmcp'), m.version('mcp'))"` prints 4.x and 2.3.x | pending |
| D11 | Goal 2: T046–T050 server and client on FastMCP, tests green | `uv run pytest` exits 0; `grep -rnE "from mcp\b\|import mcp\b\|MCPServer\|StdioServerParameters" src tests` is empty; `src/applytrail/mcp_server.py` builds no `CallToolResult`; `git diff` of `tests/` vs the pre-goal-2 commit changes only imports/call sites (`raise_on_error=False`, `list_tools()` list, `StdioTransport`) plus the one new masked-error test; no expected value changed | pending |
| D12 | Goal 2: wire contract parity (quickstart Scenarios 6–7) | `uv run fastmcp list --command "uv run applytrail-mcp" --input-schema --output-schema --json` shows exactly `search_job_emails` and `get_email` with bounds from contracts/mcp-tools.md; `APPLYTRAIL_HOME=$(mktemp -d) uv run fastmcp call --command "uv run applytrail-mcp" --target search_job_emails --input-json '{"after": "2026-04-15T00:00:00Z"}'` prints `Error: AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth.`, exits 1, no FastMCP banner | pending |
| D13 | Goal 2: T051–T053 docs and governance; lint clean | `AGENTS.md` and `README.md` name `fastmcp`; `.specify/memory/constitution.md` has a PATCH bump, Technical Constraints name `fastmcp` 4.x, Sync Impact Report updated, and the file is left uncommitted; `uv run ruff check . && uv run ruff format --check .` exits 0; T045–T053 checked in tasks.md | pending |
| D14 | Goal 2: T054 real-mailbox regression (manual) | Human runs `applytrail` and `applytrail --offline` against the real mailbox and reports same behaviour as D9; human signs off in debt.md. Maker never fakes this | pending |
| D15 | Goal 2 landed as exactly one commit | One `refactor(mcp): ...` commit on `001-gmail-sync-table` containing T045–T052 changes (code, tests, `pyproject.toml`, `uv.lock`, README, AGENTS.md, tasks.md checkboxes), constitution excluded; `uv run pytest` exits 0 at that commit | pending |
Statuses: pending → maker-ready → checker-pass | checker-fail → human-signed.

## Budget
- Max iterations: 50
- Iterations run: 23
- Goal 2 sub-budget: at most 8 more iterations (ceiling 31 total) before forced human review.
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
- Goal 2: `uv run fastmcp list` / `fastmcp call` against the local `applytrail-mcp` with an empty `APPLYTRAIL_HOME` (no Gmail call).
- NOT allowed: live Gmail API, live Ollama calls (except human-run gates D4/D9/D14), `git push`, new dependencies beyond plan.md (`fastmcp` is now in plan.md; nothing else).

## Automation trigger
- Manual: `/speckit.loop.run` per iteration, `/speckit.loop.check` from a separate session after each story commit. No scheduler/CI wired.

## Commit policy
- Work on branch `001-gmail-sync-table`, never commit on `main`.
- Commit boundaries: (1) Phases 1–2 foundation, (2) US1 / Phase 3, (3) US2 / Phase 4, (4) US3 / Phase 5, (5) Polish / Phase 6.
- Each user story = exactly one commit, made only after its phase checkpoint is green (`uv run pytest` exits 0).
- Conventional Commits: `feat(us1): ...`, `feat(us2): ...`, `feat(us3): ...`.
- Goal 2: exactly one `refactor(mcp): ...` commit for Phase 7 after D10–D13 are checker-pass. The goal-2 spec-doc edits (plan, research, contracts, quickstart, tasks Phase 7) must be committed on the branch BEFORE iteration 24, so worktree iterations see them.

## Guardrails
- Human sign-off required before done: true
- Closure exception (human, 2026-10-14): D4 may remain human-signed rather than checker-pass, with the failed zero-leak gate explicitly accepted as DEBT-001. All other criteria require checker-pass.
- Comprehension debt tracked: true
- Open blocking debt blocks done: true
- Manual gates T025 (D4) and T044 (D9) require a human run; maker pauses and records debt, never fakes RESULTS.md.
- Do not start T028+ until D4 is human-signed (tasks.md T025).
- Goal 2: tests first (T046/T047 must fail against `MCPServer` before T048). Contract expected values are frozen; changing one is checker-fail. Constitution amendment stays uncommitted for human review.

## State
- Phase: defined (goal 2 reopened the loop; goal 1 stays done and signed off)
- Last updated: 2026-10-14

- Closure sign-off: saurav-cgr explicitly signed off in chat on 2026-10-14, accepting D4's human-signed exception and the recorded risks (DEBT-001 and DEBT-002). See debt.md.
