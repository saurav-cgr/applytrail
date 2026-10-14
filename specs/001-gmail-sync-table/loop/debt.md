# Comprehension Debt & Sign-off

Every change the loop makes that a human has not yet understood is debt. Debt is
acknowledged, not deleted. The loop may not declare "done" while blocking debt is open.

## Open debt
| ID | Iteration | What changed | Why it needs human eyes | Severity | Status |
|----|-----------|--------------|-------------------------|----------|--------|
| DEBT-001 | 10 | Default model `qwen3:4b` with prompt v2 (`5405f01`) accepted although the golden gate failed: 100.0% company, 90.0% status, 1 non-job leak (golden-028). | golden-028 is a prompt injection: an email carrying a ready-made JSON answer. It leaked with every model and prompt tried (`qwen3:4b` v1/v2, `gemma3:4b`, `qwen3:8b`), so a similar real email can create a fake application row. SC-003 requires zero leaks; this is a deliberate deviation. The golden set is synthetic and the prompt was tuned on it, so real accuracy may be lower. Mitigation offered and declined for now: a deterministic guard that skips emails containing the schema's field names. | high | accepted (human, 2026-10-14); acknowledged at closure |
| DEBT-002 | 23 | D9 / T044 runs without Scenario 3b (human ruling). | SC-001 (an incremental sync of about 20 emails in under 60 s on the reference laptop) and the 3 GB memory check are never measured on real mail. The golden-set eval suggests about 2 s per email, which only estimates this. If real syncs are slow, the R3 mitigation (`BODY_MAX_CHARS = 3000`) has not been tried. | medium | accepted (human, 2026-10-14); acknowledged at closure |
| DEBT-003 | 25 | Maker smoke test made two live, read-only Gmail `search_job_emails` calls with the real token (the D12 command as first written did not isolate `APPLYTRAIL_HOME`; see M-018). The D12/quickstart command was changed to `env APPLYTRAIL_HOME=... ` inside `--command`. | This breaks the loop contract's "no live Gmail API" rule. `~/.applytrail/token.json` was refreshed (rewritten 20:54:12, mode 0600); the store was untouched and nothing was printed or kept. The human should (a) acknowledge the violation and (b) approve the maker's edit to criterion D12. | medium | closed: acknowledged and D12 edit approved (human, 2026-10-14) |
| DEBT-004 | 24–27 | FastMCP dependency/server/client migration landed as 1e8fbc5: typed model returns, ToolError prefixes, masked unexpected errors, raise_on_error=False and StdioTransport; expanded dependency tree. | The human has confirmed live behavior and approved the CLI isolation fix, but has not demonstrated understanding of the new error boundary or reviewed the migration as a whole. Explain why raise_on_error=False is necessary and which unexpected-error details are hidden, then review or explicitly acknowledge the remaining migration scope. | high | acknowledged (human, 2026-10-14); addressed at migration closure |
| DEBT-005 | 26 | Constitution PATCH draft 1.1.1 names FastMCP and updates the Sync Impact Report; principles unchanged; draft remains uncommitted. | No explicit human review of the draft is recorded. Confirm understanding of the dependency-only amendment; acknowledgement does not authorize committing it. | medium | acknowledged (human, 2026-10-14); addressed at migration closure |

## Sign-off log
| Date | Criterion / scope | Signed off by | Note |
|------|-------------------|---------------|------|
| 2026-10-14 | D4 (T025 extractor gate) | saurav-cgr (decision given in chat; recorded by the maker) | Accepted `qwen3:4b` + prompt v2 despite FAIL (1 leak, status exactly 90%). See DEBT-001 and tests/golden/RESULTS.md. Unblocks T028+. |
| 2026-10-14 | D9 (T044 quickstart, Scenarios 1–6 without 3b) | saurav-cgr (reported in chat; recorded by the maker) | All scenarios behaved as expected on a real mailbox. No timings reported. Scenario 3b skipped; see DEBT-002. |
| 2026-10-14 | Whole-loop closure; D4 exception; DEBT-001 and DEBT-002 | saurav-cgr (explicit sign-off in chat) | "Sign off, accepting D4’s human-signed exception and the recorded risks". Guard questions addressed: processed IDs and Ctrl-C resume explained; live Scenarios 1–6 personally confirmed; clarified MCP server is a separate subprocess using the same Python interpreter, connected over stdio. D9 medium-confidence report-only verification acknowledged. D4 remains human-signed, with the failed zero-leak gate accepted rather than relabeled as a checker pass. Injection leak and unmeasured SC-001 speed/memory retained as accepted debt. |
| 2026-10-14 | DEBT-003 (live Gmail calls during iteration 25 smoke test) | saurav-cgr (said "acknowledge debt 003" in chat; recorded by the maker) | Violation acknowledged. Approval of the maker's D12 command edit not yet given. |
| 2026-10-14 | D12 command edit (DEBT-003 fix: `env APPLYTRAIL_HOME=...` inside `--command`) | saurav-cgr (said "approved" in chat; recorded by the maker) | Criterion change approved; DEBT-003 closed. |
| 2026-10-14 | D14 (T054 real-mailbox regression after FastMCP migration, `1e8fbc5`) | saurav-cgr (reported in chat; recorded by the maker) | "applytrail and applytrail --offline are working as before". No timings reported. |
| 2026-10-14 | Goal 2 migration closure; DEBT-004/005; D14 verification limit; existing accepted risks | saurav-cgr (explicit answers and sign-off in chat) | Explained that raise_on_error=False is an application design choice: FastMCP otherwise raises ToolError on is_error, while False returns the result for explicit error handling. Reported no migration or constitution changes needing explanation. Answered yes to acknowledgement of DEBT-004/005, the report-only D14 checker limit, and migration sign-off with existing accepted risks. Constitution remains an uncommitted draft. |


## Goal 2 guard report — 2026-10-14

The guard reviewed iterations 24–27 since the goal-1 closure, all latest checker
verdicts and the subsequent D14 human report. No argument `signoff` was supplied;
no new human sign-off is recorded and Phase remains checked.

- Criteria gate: satisfied under the explicit D4 human-signed exception; all
  other criteria, including D10–D15, are checker-pass. No uncertain criteria.
- Comprehension gate: not satisfied. DEBT-004 is new open high-severity debt;
  DEBT-005 is new open medium-severity debt. Passing tests and a live regression
  report demonstrate behavior, not comprehension of the changed error boundary.
- Sign-off gate: not satisfied for goal 2. The earlier closure covers goal 1,
  and the D14 sign-off covers the real-mailbox regression only.
- Unattended verification: D14/V018 has medium confidence because the checker
  verified the human report rather than reproducing the live run. The human has
  already personally confirmed both commands; closure should acknowledge this
  report-only checker limit. D9/V012 has the same limit and was acknowledged at
  goal-1 closure. No independence concern is found in the current verdicts.
- Existing risk decisions: DEBT-001 injection leakage and DEBT-002 unmeasured
  timing remain accepted. DEBT-003 is closed with explicit acknowledgement and
  approval of the inside-command home-isolation fix. These are not reopened.

Questions for the human:
1. Why does the client pass raise_on_error=False, and what does an unexpected
   server error expose to the client?
2. Which parts of commit 1e8fbc5 or the constitution draft can you not explain
   to a reviewer? Review those parts before acknowledging DEBT-004/DEBT-005.
3. Do you acknowledge the report-only D14 checker limit and explicitly sign off
   goal 2 with the existing accepted injection and timing risks?

Accepting the migration without understanding its error and subprocess boundary
would be cognitive surrender; the guard does not infer understanding from the
successful live run. The next action is to answer these questions and explicitly
acknowledge the new debt and migration closure. The constitution remains a
separate uncommitted draft; closure does not commit it.

No implementation or correctness grading changed. Tests were not repeated for
this guard-only ledger update; the latest checker ran 461 tests and Ruff clean.
Direct receipt: swept migration comprehension debt and closure prerequisites
without fabricating human sign-off.


## Goal 2 guard closure — 2026-10-14

The human answered the guard questions and explicitly signed off migration
closure. The explanation correctly distinguishes the application's choice of
result-based error handling from FastMCP's default exception behavior. The human
reported no migration or constitution changes requiring explanation and
acknowledged the two new debt items, the D14 report-only checker limitation,
and the existing accepted risks. No claim is made that the human separately
explained unexpected-error masking in their response.

DEBT-004 and DEBT-005 are acknowledged, retained in the ledger, and no blocking
high-severity debt remains open. All criteria are checker-pass except the
explicitly accepted D4 human-signed exception. The goal-2 human closure sign-off
is now recorded. All closure conditions hold; Phase becomes done.

The constitution remains uncommitted. Closure authorizes no commit or push.
Direct receipt: recorded the supplied human answers and sign-off, checked the
closure conditions, and closed the loop without changing implementation.
