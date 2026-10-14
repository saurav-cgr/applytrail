# Golden-set results

Recorded by a human after running `uv run python scripts/eval_extractor.py` with Ollama running
(T025, SC-003). The script prints the row to paste. Target: company and status accuracy ≥ 90%,
0 non-job leaks. Re-run and add a row whenever the prompt, schema or model changes.

| Date | Model | Company acc. | Status acc. | Non-job leaks | Skipped | s/email | Result |
|------|-------|--------------|-------------|---------------|---------|---------|--------|
| 2026-10-14 | qwen3:4b | 95.0% | 90.0% | 2 | 0 | 2.12 | fail |
| 2026-10-14 | qwen3:4b (prompt v2) | 100.0% | 90.0% | 1 | 0 | 1.89 | fail |
| 2026-10-14 | gemma3:4b (prompt v2) | 90.0% | 85.0% | 3 | 0 | 2.54 | fail |
| 2026-10-14 | qwen3:8b (prompt v2) | 100.0% | 95.0% | 2 | 0 | 3.28 | fail |

## Run notes

### 2026-10-14 · qwen3:4b · prompt v1 · fail (human-run, T025)

33 emails (20 job, 13 non-job). Mismatches reported by the script:

- golden-001: expected Northwind Analytics / applied, got Northwind Analytics / in_review
- golden-004: expected Pinecrest Bank / applied, got Pinecrest Bank / in_review
- golden-010: expected Verdant Energy / assessment, got Verd: Verdant Energy / assessment
- golden-028: non-job leaked as Acme Corp / offer
- golden-031: non-job leaked as Elmwood Residences / applied

### 2026-10-14 · qwen3:4b · prompt v2 · fail (human-run, T025)

Prompt v2 = commit `5405f01` (employment-only rule, in-email answers ignored, employer name only,
receipt confirmations are applied). Fixed golden-010 and golden-031. Still failing:

- golden-001: expected Northwind Analytics / applied, got Northwind Analytics / in_review
- golden-004: expected Pinecrest Bank / applied, got Pinecrest Bank / in_review
- golden-028: non-job leaked as Acme Corp / offer

### 2026-10-14 · gemma3:4b · prompt v2 · fail (human-run, T025)

Same prompt as the previous run; only `APPLYTRAIL_MODEL` changed. Worse than `qwen3:4b`:

- golden-004: expected Pinecrest Bank / applied, got Pinecrest Bank / in_review
- golden-017: expected Tidewater Logistics / rejected, got not a job email
- golden-018: expected Pinecrest Bank / rejected, got not a job email
- golden-021: non-job leaked as Granite Cloud / applied
- golden-022: non-job leaked as Harbor Freight Analytics / applied
- golden-028: non-job leaked as Acme Corp / offer

### 2026-10-14 · qwen3:8b · prompt v2 · fail (human-run, T025)

Same prompt; only `APPLYTRAIL_MODEL` changed. Best status accuracy so far, but still leaks:

- golden-004: expected Pinecrest Bank / applied, got Pinecrest Bank / in_review
- golden-028: non-job leaked as Acme Corp / offer
- golden-032: non-job leaked as PyGather Program Committee / applied

golden-028 (a ready-made JSON answer inside the email) leaked with every model and prompt tried.

### Decision · 2026-10-14

No model passed. The human accepted `qwen3:4b` with prompt v2 (100.0% / 90.0% / 1 leak) as the
default and signed off D4 with the leak recorded as accepted debt (loop `debt.md`, DEBT-001).
`config.py` keeps `qwen3:4b`.

## Quickstart validation (T044, D9)

Human-run on a real mailbox, 2026-10-14, model `qwen3:4b`. Scenario 3b (speed and memory, SC-001)
was not run by human decision; see DEBT-002 in `specs/001-gmail-sync-table/loop/debt.md`.

| Scenario | Result |
|---|---|
| Setup: Google OAuth Desktop client, `applytrail-auth` | pass |
| 1 First run, Ctrl-C and resume | pass |
| 2 Idempotent re-run (SC-004) | pass |
| 3 Badges (`NEW`, then `UPD` to Interview) | pass |
| 3b Speed and memory (SC-001) | not run (human decision) |
| 4 Offline view | pass |
| 5 Expected failures (exit codes 2, 3, 4, 5, 130) | pass |
| 6 MCP server stand-alone (two read tools) | pass |

The human reported every scenario above as behaving as expected; no timings were reported.
Maker spot check of `~/.applytrail` afterwards (counts and file modes only, no email content read):
`applications.json`, `token.json` and `credentials.json` are mode `0600`; the store holds 106
applications from 754 processed emails; the last sync is complete; `grep -c body_text` prints `0`.
