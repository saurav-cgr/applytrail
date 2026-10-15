# Loop Contract

## Purpose
1. Drive every task in `specs/002-lookup-open-email/tasks.md` (T001–T049) to completion, one user story at a time (foundation → US1 → US2 → US3 → polish). After each story the maker hands off to an independent checker, and the story's commit is made **only after** the checker records `pass` for that story.

## Done-criteria
| ID | Criterion (checkable) | How the checker verifies it | Status |
|----|-----------------------|-----------------------------|--------|
| D1 | Setup + Foundational (T001–T010) done: fixture, fixture loader, `lookup.numbered`, `links.thread_url` (`u/0`), `#` column | `uv run pytest tests/unit/test_lookup.py tests/unit/test_links.py tests/unit/test_render.py tests/unit/test_fakes.py` exits 0; `uv run ruff check . && uv run ruff format --check .` exits 0; full `uv run pytest` exits 0; `tests/fixtures/store_lookup.json` loads with 7 applications in the T002 order; a 999-row table renders every line ≤ 100 columns; T001–T010 checked in tasks.md | pending |
| D2 | Foundation landed as exactly one commit, after D1 is checker-pass | `git log --oneline` shows one `feat(table): ...` commit on `002-lookup-open-email` after the spec-docs commit; `git show --stat` touches only Phase 1–2 files plus the tasks.md checkboxes; `uv run pytest` exits 0 at that commit | pending |
| D3 | US1 (T012–T019) done: `applytrail check` | `uv run pytest tests/unit/test_lookup.py tests/unit/test_render.py tests/unit/test_cli.py tests/unit/test_errors.py` exits 0; the SC-003 list has ≥ 20 variants and 10 unrelated names, and the SC-003a list has ≥ 10 typos at ≥ 90%; on a copy of `store_lookup.json`, `applytrail check acme` exits 0, `check Initech` exits 6, `check Gogle` prints `Did you mean: Google (#2)?` and exits 6, `check "&"` exits 2; store sha256 unchanged after each; `check acme` output has columns `#, First seen, Company, Role, Status, Last seen` with each line ≤ 100 columns (FR-004, DEBT-001 option A); T012–T019 checked | pending |
| D4 | US1 landed as exactly one commit, after D3 is checker-pass | One `feat(us1): ...` commit containing all Phase 3 files; ruff and `uv run pytest` green at that commit | pending |
| D5 | US2 (T021–T028) done: `applytrail open` | `uv run pytest tests/unit/test_links.py tests/unit/test_lookup.py tests/unit/test_render.py tests/unit/test_cli.py` exits 0; tests prove no real browser launch (`webbrowser.open` patched); on the fixture copy, `applytrail open 2 --print` prints `Address for Google — Software Engineer (#2)` plus a `u/0` address and exits 0; `open 99` exits 2 with the exact contract message; `open acme` exits 2 and lists rows 1 and 5; `open initech` exits 6; `grep -nE "import (mcp_client\|extractor\|sync)" src/applytrail/cli.py` shows those imports only inside `_sync_command`; T021–T028 checked | pending |
| D6 | US2 landed as exactly one commit, after D5 is checker-pass | One `feat(us2): ...` commit containing all Phase 4 files; ruff and pytest green at that commit | pending |
| D7 | US3 (T030–T043) done: synced mailbox | `uv run pytest` exits 0, including `contract/test_mcp_tools.py`, `test_mcp_client.py`, `test_gmail_client.py`, `test_models.py`, `test_store.py` and `integration/`; the contract test asserts the tool set is exactly `{search_job_emails, get_email, get_account}`; `grep -rnw "modify\|send\|trash\|batchDelete" src/applytrail/gmail_client.py` is empty; `uv run fastmcp list --command "env APPLYTRAIL_HOME=$(mktemp -d) uv run applytrail-mcp" --json` lists exactly those 3 tools (memory M-005); a store without `sync.mailbox` still loads; with a mailbox, the table link and `open --print` use `u/<percent-encoded mailbox>`; T030–T043 checked | pending |
| D8 | US3 landed as exactly one commit, after D7 is checker-pass | One `feat(us3): ...` commit containing all Phase 5 files; ruff and pytest green at that commit | pending |
| D9 | Polish (T045–T048) done | The perf test asserts < 1 s for 500 applications for `numbered`, `find` (hit and miss) and `resolve`, and passes; `README.md` documents `check`, `open`, `--print`, exit codes 0/2/6, row numbers changing after a sync, the SSH print-only behaviour, multi-account links, and `get_account`; `AGENTS.md` lists all 3 MCP tools; quickstart.md has a `## Results` section covering Q1–Q4 and Q7, with Q5 and Q6 marked pending sign-off; ruff and pytest exit 0 | pending |
| D10 | Polish landed as exactly one commit, after D9 is checker-pass | One `docs: ...` commit; ruff and pytest green at that commit | pending |
| D11 | Manual gates Q5 and Q6 (real Gmail, browser signed in to two accounts; SC-005) | Human runs quickstart Q5 and Q6 and reports the outcome; the result is recorded in quickstart.md Results; the human signs off in debt.md. The maker never fakes this | pending |

Statuses: pending → maker-ready → checker-pass | checker-fail → human-signed.

## Budget
- Max iterations: 50
- Iterations run: 0
- Isolation: worktree (per-story WIP branch; see memory M-003)
- Per-iteration scope: one test+implementation task group within a single story. Never span two stories in one iteration. A story's last iteration ends with the gate (ruff + pytest) and `Handoff: ready-for-check`, and **no commit**.
- Soft checkpoints: if a story uses more than 10 iterations, stop for human review before continuing.

## Roles
- Maker: produces work toward the criteria (/speckit.loop.run). Writes tests first and confirms they fail before implementing. Never grades itself, and never makes a story commit before the checker verdict.
- Checker: independent, adversarial grader (/speckit.loop.check). MUST be a separate agent/session from the maker. Runs the commands in "How the checker verifies it" itself, against primary sources (test runs, CLI exit codes, file contents, `git show`), never the maker's notes. Defaults to `fail` when uncertain.

## Story handoff and commit flow
1. Maker completes a story's tasks across one or more iterations on the story's WIP branch.
2. Maker runs the gate (`uv run ruff check . && uv run ruff format --check . && uv run pytest`), sets the story's criterion to `maker-ready`, and records `Handoff: ready-for-check`.
3. Checker grades the work-criterion (D1/D3/D5/D7/D9) and appends a verdict to verdicts.md.
   - `fail`: the criterion goes to `checker-fail` with reasons. The maker fixes it in the next iteration and hands off again.
   - `pass`: the criterion goes to `checker-pass`.
4. Only after `checker-pass` does the maker squash the WIP branch into one Conventional Commit on `002-lookup-open-email`. The checker then verifies the commit criterion (D2/D4/D6/D8/D10) with `git show --stat` and a pytest run at that commit.
5. The next story starts only after its commit criterion is `checker-pass`.

## Allowed tools / connectors
- Core Spec Kit workflow (file edits, shell). Serena MCP for symbol navigation and edits.
- `uv` (sync, run pytest, run ruff, run applytrail against a temporary `APPLYTRAIL_HOME`), `git` (branch, worktree, add, commit, merge --squash; no push, no force-push to `002-lookup-open-email`).
- `uv run fastmcp list` against a local `applytrail-mcp` with an empty temporary `APPLYTRAIL_HOME` set **inside** `--command` (no Gmail call).
- NOT allowed: live Gmail API or the real `~/.applytrail` store (except the human-run D11), live Ollama, launching a real browser in tests, `git push`, any new dependency (user instruction: existing stack only).

## Automation trigger
- Manual: `/speckit-loop-run` for each maker iteration, then `/speckit-loop-check` from a separate session at each story handoff. No scheduler or CI.

## Commit policy
- Branch `002-lookup-open-email`; never commit to `main`; never push.
- Before the first worktree iteration, the spec docs for 002 (spec, plan, research, data-model, contracts, quickstart, tasks, checklists, loop/) are committed as `docs(spec): ...`, with human approval, so worktrees see them.
- Commits, in order: `feat(table): ...` (Setup + Foundation), `feat(us1): ...`, `feat(us2): ...`, `feat(us3): ...`, `docs: ...` (Polish). Each is exactly one commit, made only after its work-criterion is checker-pass.
- The user's unrelated pending changes (`.specify/integrations/*.manifest.json`) are never included in loop commits.

## Guardrails
- Human sign-off required before done: true
- Comprehension debt tracked: true
- Open blocking debt blocks done: true
- Tests first (Constitution VIII, user instruction): every test task is run and seen failing before its implementation. Expected strings come from contracts/cli.md and are frozen; changing one is checker-fail unless a human ruling is recorded.
- Analysis finding C1 (FR-004 first-seen date): resolved 2026-10-15 (DEBT-001, option A).
- D11 is human-only; the maker pauses and records it, and never fabricates results.

## State
- Phase: defined
- Last updated: 2026-10-15
