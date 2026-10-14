# Comprehension Debt & Sign-off

Every change the loop makes that a human has not yet understood is debt. Debt is
acknowledged, not deleted. The loop may not declare "done" while blocking debt is open.

## Open debt
| ID | Iteration | What changed | Why it needs human eyes | Severity | Status |
|----|-----------|--------------|-------------------------|----------|--------|
| DEBT-001 | 10 | Default model `qwen3:4b` with prompt v2 (`5405f01`) accepted although the golden gate failed: 100.0% company, 90.0% status, 1 non-job leak (golden-028). | golden-028 is a prompt injection: an email carrying a ready-made JSON answer. It leaked with every model and prompt tried (`qwen3:4b` v1/v2, `gemma3:4b`, `qwen3:8b`), so a similar real email can create a fake application row. SC-003 requires zero leaks; this is a deliberate deviation. The golden set is synthetic and the prompt was tuned on it, so real accuracy may be lower. Mitigation offered and declined for now: a deterministic guard that skips emails containing the schema's field names. | high | accepted (human, 2026-10-14) |

## Sign-off log
| Date | Criterion / scope | Signed off by | Note |
|------|-------------------|---------------|------|
| 2026-10-14 | D4 (T025 extractor gate) | saurav-cgr (decision given in chat; recorded by the maker) | Accepted `qwen3:4b` + prompt v2 despite FAIL (1 leak, status exactly 90%). See DEBT-001 and tests/golden/RESULTS.md. Unblocks T028+. |
