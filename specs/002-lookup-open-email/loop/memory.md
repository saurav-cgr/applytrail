# Loop Memory

Conventions, decisions, and dead ends that should survive between runs so the
loop never re-derives or re-litigates them. Keep entries short and durable.

- [M-001] Story flow: maker finishes the story → gate green → `maker-ready` → independent checker verdict → commit **only after checker-pass** (user instruction, 2026-10-15). The maker never commits story code before the verdict. (define, 2026-10-15)
- [M-002] Branch `002-lookup-open-email`; never commit to `main`; never push. One commit each for foundation (`feat(table)`), US1, US2, US3 and polish (`docs`). Never stage `.specify/integrations/*.manifest.json` (the user's unrelated changes). (define, 2026-10-15)
- [M-003] Worktree layout, carried over from 001 (M-008/M-009 there): each story's code accumulates on a WIP branch (`us1-wip`, …) as `wip(<story>): ...` commits, in a fresh worktree per iteration (`git worktree add ../applytrail-002-iter-<n> <story>-wip`). Loop bookkeeping (`loop/*.md`) is edited in the main copy. After checker-pass, land it with `git merge --squash <story>-wip` as the single story commit, then delete the WIP branch. The spec docs must be committed first (`docs(spec): ...`), or worktrees won't see them. (define, 2026-10-15)
- [M-004] Existing stack only, no new dependency (user instruction). Stdlib `difflib`, `webbrowser` and `urllib.parse` cover lookup, suggestions, browser and address building. (define, 2026-10-15)
- [M-005] The `fastmcp` CLI does not forward the caller's environment: set `APPLYTRAIL_HOME` inside `--command` (`env APPLYTRAIL_HOME=<tmp> uv run applytrail-mcp`), or the server uses the real token and calls live Gmail (001 memory M-018). (define, 2026-10-15)
- [M-006] Known fixes to apply while implementing (analysis 2026-10-15). U1: move `sort_key` into `lookup.py`, with `render.py` importing it (the import cycle is certain). U2: the 100-column guarantee holds up to 999 rows. A1: skip T010; T046 covers the README. (define, 2026-10-15)
- [M-008] `check` output (and `open` when several match) uses `build_check_table`: `#, First seen, Company ≤ 25, Role ≤ 21, Status, Last seen`, no badge column. The main table keeps badges and has no First seen (human ruling DEBT-001 option A, 2026-10-15). (define, 2026-10-15)
- [M-007] Existing tests that must change, not be deleted: the `test_render.py` widths `[4, 28, 30, 12, 10]` and the ellipsis bounds of 28/30 (T006), and the `test_mcp_tools.py` tool-set assertions near lines 73 and 259 (T034). The `u/0` link test stays until US3. (define, 2026-10-15)
