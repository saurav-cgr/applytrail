# Loop Memory

Conventions, decisions, and dead ends that should survive between runs so the
loop never re-derives or re-litigates them. Keep entries short and durable.

- [M-001] One git commit per user story (US1, US2, US3); foundation and polish get their own commits. Commit only when the phase checkpoint is green. (defined, 2026-10-14)
- [M-002] Branch `001-gmail-sync-table`; never commit to `main`; never push. (defined, 2026-10-14)
- [M-003] Extraction via local Ollama `qwen3:4b` over stdlib `urllib`; no `google-genai`, no `ollama` package (research R2). (defined, 2026-10-14)
- [M-004] Tests before implementation; run and confirm failing first (Constitution VIII). Tests never call Gmail or a live model. (defined, 2026-10-14)
- [M-005] Work in place on branch `001-gmail-sync-table` until the foundation commit (D2); iteration-1 work is uncommitted, so a worktree would miss it. User's pending changes were committed separately first (db66332..6e197b3, human decision 2026-10-14). Use worktrees from the commit after D2. (iteration 1, 2026-10-14)
- [M-006] Ruff excludes `.specify` and `specs` (vendored scripts, markdown code blocks). `pyproject.toml` has no `readme` until T043 adds `README.md`. (iteration 1, 2026-10-14)
- [M-007] `FakeMcpClient.search_job_emails` returns the contract `structured_content` dict (`messages`, `next_page_token`, `query`); `get_email` returns `EmailMeta`. `GmailMcp` (T020) must keep the same shapes. (iteration 2, 2026-10-14)
- [M-008] Each done-criterion that says "one commit" is strict (human ruling, 2026-10-14): fixes to an already-committed phase are folded into that phase's commit and later commits replayed (cherry-pick, no push); keep a `backup/...` branch first. Worktrees use a temporary branch (`loop-iter-<n>`) fast-forwarded into the feature branch, because one branch cannot be checked out twice. (iteration 3, 2026-10-14)
