# Comprehension Debt & Sign-off

Every change the loop makes that a human has not yet understood is debt. Debt is
acknowledged, not deleted. The loop may not declare "done" while blocking debt is open.

## Open debt
| ID | Iteration | What changed | Why it needs human eyes | Severity | Status |
|----|-----------|--------------|-------------------------|----------|--------|
| DEBT-001 | define | Analysis C1: FR-004 and US1 scenario 1 require each `check` match to show its first-seen date, but the planned output (shared table) has only "Last seen". | A human must choose: add first seen to the `check` output (and to T014/T018), or remove it from FR-004. Blocks D3. | blocking | resolved 2026-10-15: option A |

## Sign-off log
| Date | Criterion / scope | Signed off by | Note |
|------|-------------------|---------------|------|
| 2026-10-15 | DEBT-001 / FR-004 | saurav-cgr (chat) | Chose option A: keep first seen, shown only in the `check` table, which replaces the badge column with First seen (Role ≤ 21). Main table unchanged. Spec FR-004, contracts/cli.md, and tasks T014/T018/T024/T028 updated. |
| 2026-10-15 | Spec-docs commit | saurav-cgr (chat) | Approved committing the 002 spec docs as `docs(spec): ...` before the first worktree iteration. |
