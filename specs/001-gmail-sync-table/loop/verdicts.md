# Checker Verdicts

A criterion is `pass` only after the checker confirmed it against the PRIMARY
source (a run, a file, an endpoint), not the maker's self-assessment.

| ID | Iteration | Criterion | Method (primary source) | Verdict | Confidence | Date |
|----|-----------|-----------|-------------------------|---------|------------|------|
| V001 | 2 | D1 | Independent `uv sync` (exit 0), targeted pytest (68 passed), full pytest (101 passed), Ruff lint/format (exit 0); source and task audit; adversarial probes below violate T007/T012 and the store contract | fail | high | 2026-10-14 |
| V002 | 2 | D2 | `git log --oneline -8`, `git show --stat 68e21e2`: one foundation commit, 34 files confined to T001–T014; `git diff 68e21e2 HEAD -- src tests pyproject.toml uv.lock specs/001-gmail-sync-table/tasks.md` empty | pass | high | 2026-10-14 |
| V003 | 3 | D1 | Independent uv sync exit 0; targeted pytest 82 passed; full pytest 115 passed; Ruff lint/format exit 0; source/task audit and disposable-directory schema, completion, corrupt-destination, temporary-symlink/failed-rename probes | pass | high | 2026-10-14 |
| V004 | 3 | D2 | git log and git show --stat 7818ce5: exactly one foundation commit, 34 Phase 1–2 files; git diff 7818ce5 HEAD -- src tests pyproject.toml uv.lock specs/001-gmail-sync-table/tasks.md empty | pass | high | 2026-10-14 |
| V005 | 14 | D3 | Clean detached worktree at us1-wip b570565; independent full pytest 424 passed, Ruff lint/format passed, US1 task checkboxes audited; synthetic role, debug privacy and malformed .env probes reproduce failures below | fail | high | 2026-10-14 |
| V006 | 15 | D3 | Clean detached worktree at us1-wip 865e255; independent full pytest 428 passed, Ruff lint/format passed, US1 tasks checked; literal-role, exception-chain/notes privacy and real malformed .env probes passed | pass | high | 2026-10-14 |
| V007 | 16 | D5 | Exact commit d3fa14b in clean detached worktree: 428 pytest tests passed, Ruff lint/format passed; git history has exactly one feat(us1) commit; full non-loop tree matches reviewed 865e255; task and changed-path audit passed | pass | high | 2026-10-14 |
| V008 | 19 | D6 | Clean detached worktree at 7ebc719: required 66 tests and full 449 tests pass, Ruff passes; single US2 commit and task audit pass; independent search-failure probes retain stale badges and count prior additions in latest run, violating T036/data-model | fail | high | 2026-10-14 |
| V009 | 20 | D6 | Clean detached worktree at fae030f: required 68 tests and full 451 tests pass, Ruff passes; single US2 commit/task audit; nine independent search, pagination and progress stop probes plus save/load/render and unchanged repeat pass | pass | high | 2026-10-14 |
| V010 | 22 | D7 | Clean detached worktree at fa757fd: required 35 tests and full 460 tests pass, Ruff passes; single US3 commit/task audit; independent fresh-process offline probes forbid sockets, subprocesses, writes and network imports; 500 rows render in 0.27–0.30 s | pass | high | 2026-10-14 |
| V011 | 23 | D8 | Clean detached worktree at 8fc7e1e: uv sync, Ruff lint/format and full pytest (460) pass; provider/write-call searches and AST audit empty; README/task/constitution audit; temporary uv tool install and installed-command probes pass | pass | high | 2026-10-14 |
| V012 | 23 (post-iteration human gate) | D9 | Clean feature tree dc6049b: RESULTS.md six scenario records, debt.md human sign-off and accepted 3b waiver audited against revised contract; no implementation drift; 460 tests and Ruff pass; live run not independently repeated | pass | medium | 2026-10-14 |
| V013 | 24 | D10 | Clean fastmcp-wip worktree at 468b84d: independent uv sync exits 0; installed fastmcp 4.1.0 and mcp 2.3.0; manifest/lock assertions exclude direct mcp and retain Python >=3.11; T045 checked; 460 pytest tests and Ruff lint/format pass | pass | high | 2026-10-14 |
| V014 | 25 | D11 | Clean fastmcp-wip at 3ac0041: 461 pytest tests, Ruff lint/format, source/import audit and frozen-assertion comparison pass; independent invalid-input, boundary, JSON/error and isolated stdio probes pass; two new assertions fail on pre-migration source | pass | high | 2026-10-14 |
| V015 | 26 | D12 | Clean fastmcp-wip at 48dd4b1: real FastMCP CLI over isolated stdio lists exactly two tools with contractual schemas; call exits 1 with exact AUTH_REQUIRED text; no banner; explicitly passed temporary home stays empty | pass | high | 2026-10-14 |
| V016 | 26 | D13 | Migration docs and T045–T053 checkboxes audited at 48dd4b1; main-copy constitution 1.1.1 PATCH report and unchanged principles verified, draft unstaged/uncommitted; Ruff passes and 461 tests pass | pass | high | 2026-10-14 |
| V017 | 27 | D15 | Feature branch at 1e8fbc5: exactly one refactor(mcp) commit since 3a091e5; tree identical to reviewed 48dd4b1 and backup; exact nine intended paths, constitution excluded; no implementation drift; 461 pytest tests and Ruff pass | pass | high | 2026-10-14 |

## Iteration 2 independent check — 2026-10-14

The checker did not produce either maker iteration in this session. Checked the clean in-place
feature branch at `bc1b182`, the location used by iteration 2. No implementation or iteration
records were edited. There is one checker vote; the contract requests no additional votes.

### D1 failures

1. **Invalid store versions are silently accepted.** `Store.model_validate` accepts JSON
   `schema_version: true` and `schema_version: 1.0` as integer `1`. T007 requires version 1;
   contracts/store-schema.md requires refusal on an unknown version or validation failure.
   Pydantic's literal equality admits these distinct JSON types. Add a pre-validation check
   requiring an integer (excluding boolean) equal to 1, and regression tests through `load`.
2. **Completion does not consistently imply zero pending emails.**
   `SyncState(last_sync_complete=True, pending=2)` succeeds with `stop_reason=None`. T007 and
   data-model.md require zero pending when complete. The validator checks only `stop_reason`.
   Extend the existing check to cover `last_sync_complete`, with a regression test.
3. **Saving bypasses corruption protection.** `load` rejects a file containing `{corrupt`, but
   `save(Store.empty(), path)` overwrites that same file. The store contract explicitly promises
   refusal to load and refusal to write on validation failure. Check an existing destination
   before replacement and prove its bytes remain intact when invalid.
4. **A temporary symlink defeats atomicity.** If `applications.json.tmp` points to
   `applications.json`, `os.open` follows it and truncates the original. Injecting a rename
   failure then leaves the original changed, contrary to T011/T012's atomic-write guarantee.
   Reject temporary symlinks at open time, or use an exclusively created temporary file;
   add a regression test that preserves the original bytes.

These probes used disposable directories and the installed project interpreter; no Gmail,
Ollama, credentials, or real application data were accessed. The existing tests do not cover
these inputs. Reproduce with `.venv/bin/python` from the repository root:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from applytrail import store
from applytrail.errors import StoreUnreadable
from applytrail.models import Store, SyncState

for version in (True, 1.0):
    data = Store.empty().model_dump(mode="json")
    data["schema_version"] = version
    print("accepted version:", version, Store.model_validate(data).schema_version)
print("accepted completion:", SyncState(last_sync_complete=True, pending=2))

with TemporaryDirectory() as directory:
    path = Path(directory) / "home" / "applications.json"
    path.parent.mkdir()
    path.write_bytes(b"{corrupt")
    try:
        store.load(path)
    except StoreUnreadable:
        print("load rejected corrupt file")
    store.save(Store.empty(), path)
    print("corrupt file overwritten:", path.read_bytes() != b"{corrupt")
    path.with_name(path.name + ".tmp").symlink_to(path)
    original = path.read_bytes()
    real_replace = store.os.replace

    def fail_replace(src, dst):
        raise OSError("simulated rename failure")

    store.os.replace = fail_replace
    try:
        changed = Store.empty()
        changed.sync.pending = 5
        store.save(changed, path)
    except OSError:
        print("original changed despite failed rename:", path.read_bytes() != original)
    finally:
        store.os.replace = real_replace
```

### Scope and routing

D2 passes independently of D1's correctness failures. T001–T014 are checked in tasks.md;
all foundation code remains identical to commit `68e21e2`. The plan records the older
constitution's provider/SDK mismatch and recommends an amendment; this checker does not
change that policy or claim the amendment is complete.

No targeted criterion is uncertain; no comprehension-debt item was opened. D3–D9 remain
pending and were not graded. Run `/speckit.loop.run` to address D1 before advancing to US1.
This check does not close the loop; final closure still requires `/speckit.loop.guard` and
human sign-off.

## Iteration 3 independent re-check — 2026-10-14

Checked clean branch `001-gmail-sync-table` at `19ff626`. This checker session did not
produce maker iteration 3. The isolation worktree was removed after integration; checks
ran against the integrated feature branch. One checker vote; no additional votes required.
Implementation and `iterations.md` remain untouched.

### D1: pass

`uv sync` exited 0. The exact contracted targeted test command passed 82 tests;
`uv run pytest` passed all 115. Both Ruff checks exited 0. T001–T014 are checked;
package, errors, configuration, models, normalization, store, fixtures and fakes exist.

Independent `uv run python` assertions against the installed implementation confirmed:

- Versions `True`, `1.0`, `"1"`, `None`, `0`, and `2` raise `ValidationError`.
- Completion through the flag, stop reason, or both rejects `pending=2`.
- Saving over malformed JSON or a boolean schema version raises `StoreUnreadable`
  and preserves the original bytes.
- With the temporary path symlinked to the destination, an injected `os.replace`
  failure preserves original bytes and removes the temporary entry. A subsequent
  successful save with the same symlink setup round-trips `pending=5` safely.

These probes used `TemporaryDirectory` and `unittest.mock.patch.object`, with assertions
on exceptions, bytes, loaded state and temporary-file removal. Regression tests in
`tests/unit/test_models.py` and `tests/unit/test_store.py` retain the previous failure cases.
All four V001 failures are resolved; V003 supersedes that failure for current code.

### D2: pass

The current branch contains exactly one foundation commit, `7818ce5`, including the store
fixes. Its 34 files remain confined to T001–T014. No foundation implementation, tests,
package metadata, lockfile or task status changed after that commit (scoped diff empty).
V004 re-establishes the verdict against the rewritten history; V002 remains historical.

### Routing and limits

No failures or uncertain targeted criteria; no new debt opened. D3–D9 remain pending and
unchecked. Continue with `/speckit.loop.run`. This is not loop closure: all criteria must
pass before `/speckit.loop.guard` and human sign-off. No live Gmail/Ollama or minimum-Python
runtime checks were performed. The existing constitution/provider mismatch remains a
planned governance follow-up, not a completed amendment.

## Iteration 14 independent check — 2026-10-14

This checker session did not produce the implementation under review. The feature branch
contains the loop records, while the implementation is on `us1-wip` at `b570565`.
Checks ran in a clean detached worktree at that exact commit, not against the older
implementation on the feature branch. Configuration requires one independent vote.
No implementation or `iterations.md` changes were made.

### D3: fail (high confidence)

`uv run pytest` passed all 424 tests, including the required Gmail, MCP contract,
extractor, merge, first-run sync, render and CLI suites. Both Ruff checks passed
(40 files formatted). All T015–T024 and T026–T033 checkboxes are checked on `us1-wip`.
Source inspection confirmed the read-only Gmail tools and deterministic orchestration.
Passing existing tests does not cover the following adversarial failures.

1. **Untrusted role text is interpreted as Rich markup.** `render.py:47` passes
   `app.role` directly to `Table.add_row`, unlike the company cell, which uses `Text`.
   A valid extraction with role `Engineer [/bad]` passes validation and merge, but
   `render_table` raises `MarkupError`: `closing tag '[/bad]' at position 9 doesn't
   match any open tag`. Role `[bold]Engineer[/bold]` silently loses its literal tags.
   This breaks T030–T031's readable rendering for valid stored data and the untrusted
   data boundary. Smallest fix: wrap the role cell in `Text`, with a regression test
   proving literal brackets render without an exception or unintended styling.
2. **Debug tracebacks persist full email content.** With `APPLYTRAIL_DEBUG=1`, a
   synthetic sync exception whose message is a complete email body causes
   `cli.py:117` to write that body verbatim into `debug.log`. The probe asserted
   the complete synthetic body was present and confirmed exit 1. File permissions
   do not satisfy Constitution Principle V's prohibition on logging full bodies.
   Smallest fix: record traceback frames and exception types without arbitrary
   exception messages, including chained exceptions; add a privacy regression test.
   Debug opt-in does not waive this rule.
3. **Setup failures bypass the CLI error handler.** In a disposable current
   directory, an actual `.env` containing bytes `APPLYTRAIL_MODEL=\xff\n` makes
   `cli.main([])` raise `UnicodeDecodeError` instead of returning an error code.
   `load_dotenv` and `Settings.from_env` run before the `try` at `cli.py:41`.
   The installed entry point therefore prints a stack trace for this setup failure,
   violating the terminal error contract and T032–T033's unexpected-error handling.
   Smallest fix: include environment loading and settings construction in guarded
   startup, with a fallback error message when settings are unavailable; test a real
   malformed `.env` without contacting services.

The role probes constructed `EmailMeta`, `Extraction` and `Store.empty()`, called
`merge.apply`, then rendered through `Console(file=StringIO(), width=100, no_color=True)`.
The privacy probe used a temporary `APPLYTRAIL_HOME`, patched `_sync_command` to raise
`RuntimeError` containing synthetic body text, and inspected the resulting log. The
environment probe changed into a temporary directory, wrote the invalid bytes and
patched `_sync_command` to prohibit service calls. All probes used installed code at
`b570565`. The uv cache access initially failed in the sandbox; reruns used approved
escalation. No real mailbox, credentials, application store or live model was accessed.

### Scope and routing

Only D3 was maker-ready and targeted. D1/D2 retain their earlier verdicts; D4 retains
the human-accepted deviation recorded in DEBT-001. Pending US2 behavior (badge tracking,
pending counts and interruption metadata), US3 offline behavior and D5 commit squashing
were not graded as D3 failures. No targeted criterion is uncertain; no new debt opened.

Run `/speckit.loop.run` to fix these failures before the US1 squash, then request an
independent re-check. D3 is `checker-fail`; phase is `checked`. This is not loop closure.
Live Gmail/Ollama, real-mail accuracy and minimum-Python execution remain unchecked.

## Iteration 15 independent re-check — 2026-10-14

This checker session did not produce maker iteration 15. Checked `us1-wip` at
`865e255` in a clean detached worktree. The feature branch holds the current loop
records but has not yet integrated US1. One independent vote is required. Existing
uncommitted verdict text was preserved; implementation and `iterations.md` remain
untouched.

### D3: pass (high confidence)

Independent `uv run pytest` passed all 428 tests, including every suite named by D3.
Ruff lint and format checks exited 0 (40 files formatted). Required US1 task
checkboxes are checked on the reviewed branch. The diff from `b570565` is confined
to the three V005 fixes, their regression tests and the debug-log contract wording.

Independent adversarial probes against installed code established:

- Roles `Engineer [/bad]`, `[bold]Engineer[/bold]` and
  `[link=https://example.test]X` remain literal `Text` cell values and render
  without markup exceptions. This resolves V005's role rendering failure.
- With debug enabled, explicit and implicit exception chains containing a complete
  synthetic email body retain traceback frames and exception types, while omitting
  that body. Exception notes also omit the body. A cyclic cause chain terminates
  and retains both exception types. Each CLI run returns 1 with one stderr line;
  the resulting log has mode 0600. This resolves V005's exception-message leak.
- An actual `.env` with bytes `APPLYTRAIL_MODEL=\xff\n` in a temporary current
  directory returns 1 with one actionable stderr line naming `UnicodeDecodeError`,
  without a traceback. A patched sync entry point confirms no services are called.
  This resolves V005's unguarded environment-loading failure.

Probes used `TemporaryDirectory`, synthetic `EmailMeta`/`Extraction`, `StringIO`
consoles, environment patches and a patched `_sync_command`. No real application
store, mailbox, credentials or live model was accessed. The implementation tests
retain all three regression cases. V006 supersedes V005 for current D3 code.

### Scope and routing

No targeted failures or uncertain criteria; no new comprehension debt. D1/D2 retain
their prior verdicts; D4 retains its human-accepted deviation (DEBT-001). D5–D9 are
pending and were not graded. In particular, this pass does not certify the future
US2 interruption/badge behavior, US3 offline command or the US1 commit boundary.

Continue with `/speckit.loop.run` for D5, integrating US1 as exactly one story commit.
The loop is not done; final closure still requires all remaining criteria and
`/speckit.loop.guard` with human sign-off. Live Gmail/Ollama, real-mail accuracy and
minimum-Python execution remain unchecked. The accepted extraction injection risk
and planned constitution/provider amendment remain outstanding limitations.

## Iteration 16 independent check — 2026-10-14

This checker did not produce maker iteration 16 or the US1 implementation. Only
D5 was maker-ready; configuration requires one independent vote. Verification ran
in a clean detached worktree at `d3fa14b`, not merely at current HEAD.

### D5: pass (high confidence)

- Feature-branch history contains exactly one `feat(us1):` commit:
  `d3fa14b feat(us1): sync Gmail job emails into a local table`. It has one parent.
- Audited all 68 changed paths: Phase 3 modules, tests, golden fixtures/evaluation
  records and supporting model/store/fake and spec changes. No loop records or
  credentials, token, environment or application-store files are included.
- Attempted to detect omitted squash changes by comparing the complete tree to
  `backup/pre-squash-us1` at `865e255`. Differences are confined to loop records;
  all implementation, tests and supporting artifacts match the V006-reviewed tree.
  Commits after `d3fa14b` also change only loop records.
- At the exact story commit, T015–T033 are checked, while T034–T044 remain pending.
  Required Gmail/auth, MCP, extractor, merge, sync, render and CLI modules are all
  included in the story commit.
- Independent `uv run pytest`: 428 passed in 6.91 seconds on Python 3.14.7.
  `uv run ruff check .` and `uv run ruff format --check .`: pass, 40 files formatted.
  Worktree status remained clean. Initial uv cache access was blocked by the sandbox;
  the approved escalated rerun succeeded.

No failures, uncertain criteria or new debt. Implementation and `iterations.md`
were not edited. D1–D3 retain prior passes; D4 retains its human-accepted DEBT-001
deviation. D6–D9 remain pending. Continue with `/speckit.loop.run` for US2 (D6).
This is not loop closure; final closure still requires the remaining criteria and
`/speckit.loop.guard` with human sign-off.

Live Gmail/Ollama and minimum-Python execution were not checked. The accepted
extraction injection risk and planned constitution/provider amendment remain.

## Iteration 19 independent check — 2026-10-14

This checker did not produce maker iterations 17–19. Only D6 was maker-ready;
configuration requires one independent vote. Checks ran in a clean detached
worktree at the exact story commit `7ebc719`.

### D6: fail (high confidence)

Independent required merge/incremental-sync/render suites: 66 passed. Full pytest:
449 passed in 7.01 seconds on Python 3.14.7. Ruff lint and format checks passed
(41 files). History has exactly one `feat(us2):` commit, with seven files scoped
to US2 and T034–T037 checked. The squash tree matches `backup/pre-squash-us2`
outside loop records; later changes also affect only loop records. An independent
successful repeat using the same fixture confirmed unchanged applications,
zero read/added/updated counts and empty badge lists.

**Failure: badges reset after search, contrary to the run-start contract.**
`src/applytrail/sync.py:55–59` calls `_candidates` and the initial progress callback
before clearing `sync.added`/`sync.updated`. T036 explicitly says to reset at run
start; data-model.md's SyncState section says the lists represent the latest run
and reset at the start of every sync run. There is no approved exception for
search failures. The maker record flags this decision but does not amend the
contract. The existing test
`test_network_failure_during_search_keeps_previous_badges_and_state` asserts the
conflicting behavior rather than verifying the contract.

Independent reproduction at `7ebc719`: perform a successful first run using
`confirm_acme_backend`, then copy that store and have the next search raise each
of `NetworkUnavailable`, `GmailRateLimited` and `KeyboardInterrupt`. All three
retain `added=['acme|backend engineer']`; `_finish` records `read=0, added=1` for
the latest, incomplete run. Saving/loading each result through the real store
and rendering at 100 columns with no color still displays `NEW`. The save in
this probe was explicit; source inspection confirms the CLI saves exits 3, 4
and 130 and displays the table on exit 4. Thus a rate limit before processing
any email displays a stale badge, and persisted run counts describe a prior
run's additions as this run's work. No live services or user data were used.

Smallest fix for the maker: initialize the start snapshot and clear both badge
lists before search or any progress callback can fail. Replace the preservation
expectation with regression checks for empty badges and zero added/updated
counts on search failure/Ctrl-C, preserving application data, processed IDs and
checkpoint. Keep US2's single-story commit boundary when landing the correction;
request an independent re-check. The checker made no implementation or
`iterations.md` changes.

### Scope and routing

No uncertain criteria or new debt. Using `network` for non-Ollama/non-interrupt
AppErrors is not an additional failure: the current schema has no rate-limit
literal and the value does not drive fetching. D1–D3/D5 retain earlier passes;
D4 retains human-accepted DEBT-001. D7–D9 remain pending and were not graded.
Run `/speckit.loop.run` to address V008. D6 is `checker-fail`; phase is `checked`.
The loop is not done.

Live Gmail/Ollama, real-mail accuracy and minimum-Python execution were not
checked. Accepted extraction injection risk and the planned constitution/provider
amendment remain outstanding.


## Iteration 20 independent check — 2026-10-14

The checker did not produce the maker's implementation or iteration 20. D6 is
the only maker-ready criterion; one independent vote is required. Verification
ran in a clean detached worktree at replacement US2 commit `fae030f`.

### D6: pass (high confidence)

- Full pytest: 451 passed in 6.92 seconds on Python 3.14.7. Required
  merge/incremental-sync/render suites: 68 passed in 0.19 seconds. Ruff lint and
  format checks passed (41 files).
- Source inspection confirms the start snapshot and both badge resets precede
  search and the initial progress callback, satisfying T036 and SyncState's
  every-run reset rule. Compared with V008's `7ebc719`, implementation changes
  are limited to moving this initialization; the conflicting preservation test
  is replaced with three failure regressions.
- Independent probes seeded both previous badge lists, then raised each of
  NetworkUnavailable, GmailRateLimited and KeyboardInterrupt at first search,
  second search page and initial progress (nine combinations). Every stop cleared
  both lists, recorded zero read/added/updated counts, preserved applications,
  processed IDs and checkpoint, and recorded pending=0 for search failure or
  pending=1 after successful search. Explicit real store save/load and rendering
  at 100 columns without color showed no stale NEW/UPD badges. These probes did
  not execute the CLI or call live services.
- An independent successful repeat of the same fixture confirmed zero
  read/added/updated counts, empty badge lists and unchanged applications.
- Feature history contains exactly one `feat(us2):` commit, `fae030f`, with seven
  files confined to US2 and T034–T037 checked. Changes from that commit to the
  feature tip affect only loop records. The rewritten story fixes V008 while
  preserving the single-story commit boundary. V008 remains historical evidence
  against its named original commit, not a claim about the replacement.

No failures, uncertain criteria or new debt. D6 is checker-pass; phase is checked.
Implementation and iterations.md were not edited. D1–D3/D5 retain prior passes;
D4 retains its human-accepted DEBT-001 deviation. D7–D9 remain pending and were
not graded. Continue `/speckit.loop.run` for US3 (D7); passing D6 does not close
the loop. Closure still requires remaining criteria and `/speckit.loop.guard`
with human sign-off.

Live Gmail/Ollama and minimum-Python execution were not checked. Accepted
extraction injection risk and the planned constitution/provider amendment remain.


## Iteration 22 independent check — 2026-10-14

This checker did not write the US3 implementation or maker iterations 21–22.
D7 is the only maker-ready criterion; configuration requires one independent
vote. Verification ran in a clean detached worktree at exact story commit
`fa757fd`.

### D7: pass (high confidence)

- Independent full pytest: 460 passed in 7.50 seconds on Python 3.14.7.
  Required CLI/performance suites: 35 passed in 0.84 seconds. Ruff lint and
  format passed (42 files). The performance test asserts under 2 seconds for
  all 500 rows through the real offline CLI.
- Feature history contains exactly one `feat(us3):` commit (`fa757fd`), with
  five files confined to CLI, rendering, their tests and T038–T040 checkmarks.
  The feature tip differs from this story commit only in iterations.md,
  loop.md and memory.md. Source inspection confirms the offline branch loads and renders
  without constructing Gmail, MCP or Ollama clients or saving the store.
- Independent fresh-interpreter probes installed an audit hook before importing
  the CLI, rejecting socket activity, child-process creation, filesystem writes,
  mkdir, chmod, removal and rename. Each successful invocation also asserted
  that sync, extractor, mcp_client, mcp and googleapiclient were not imported.
  Missing home, invalid schema, invalid encoding, never-synced empty and synced
  empty stores returned the expected exit codes/messages without changing the
  store bytes, mtime or mode. Missing-home invocation created no directory;
  corrupt stores exited 5 with an actionable message and no traceback.
- Independent synthetic 500-row probes covered complete, incomplete/pending=230
  and incomplete/pending=0 states in Asia/Kolkata. Fresh processes rendered all
  rows in newest-first order, preserved both stored badge types, treated invalid
  Rich tags in roles literally, converted 08:02 UTC to 13:32 local time and
  produced lines no wider than 100 columns. Elapsed time including interpreter
  startup was 0.294, 0.276 and 0.273 seconds respectively. Store contents,
  nanosecond mtime and mode remained unchanged; forbidden-action hooks held.
- Reviewed the maker's empty-store distinction: a store from a completed sync
  with zero applications prints the existing empty-table message and last-sync
  footer; a never-synced empty store prints the first-sync hint. This satisfies
  US3's saved-data versus no-saved-data scenarios. The no-pending incomplete
  footer accurately names the unfinished state and the resume command.

No failures, uncertain criteria or new debt. D7 is checker-pass; phase is checked.
Implementation and iterations.md were not edited. Earlier verdicts and D4's
human-accepted DEBT-001 remain in force. D8 and D9 remain pending and were not
fully graded. Continue `/speckit.loop.run` for polish (D8). The loop remains open;
closure still requires the remaining gates and `/speckit.loop.guard` with human
sign-off.

Live Gmail/Ollama and minimum-Python execution were not checked. Accepted
extraction injection risk and the planned constitution/provider amendment remain.


## Iteration 23 independent check — 2026-10-14

The checker did not produce iteration 23, the README or the constitution amendment.
D8 is the only maker-ready criterion; one independent vote is required. Checks
ran in a clean detached worktree at `8fc7e1e`, including polish commit `16af966`,
the recorded human whole-word grep ruling and committed constitution 1.1.0.
This verifies the current tree rather than the earlier uncommitted draft state.

### D8: pass (high confidence)

- Independent `uv sync` passed. Ruff lint and format passed (43 files).
  Full pytest: 460 passed in 7.30 seconds on Python 3.14.7.
- Forbidden-provider source search was empty. Whole-word Gmail-write search
  was empty, including delete, insert, untrash and batchModify in addition to
  the contract's modify/send/trash/batchDelete. Independent AST inspection found
  no calls to those write methods. Source review confirms Gmail list/get only,
  gmail.readonly only, and exactly the two documented read tools. The required
  sender field is not a write operation; the recorded human ruling resolves the
  earlier substring false positive. T043's historical substring wording remains
  superseded by that ruling in D8.
- T041–T043 are checked. README covers installation, OAuth Desktop client and
  read-only consent, local Ollama setup, flags, all four environment variables,
  exit codes, privacy and persisted fields, file modes, and standalone MCP
  setup. Defaults, keep_alive=5m, lazy offline path and warning behavior match
  the source and CLI contract. No prompt, model or extraction schema changed.
- Constitution 1.1.0 contains the Sync Impact Report and all T042 changes:
  Python 3.11+, MCPServer/mcp 2.x, stdlib urllib/local Ollama, qwen3:4b,
  reference-laptop performance target and local/remote-host privacy wording.
  The earlier constitution/provider mismatch is resolved in the current tree.
- Independent package metadata checks confirm Python >=3.11, Markdown content
  type and the complete README as the installed package description.
  Executed the README's `uv tool install .` with temporary tool/bin directories;
  it succeeded and installed all three named entry points. Installed version,
  help and no-data offline commands returned their expected text and exit 0;
  offline created no home folder. Installed auth with missing credentials
  returned exit 2 and the README setup hint without a traceback. These probes
  used disposable state and made no live Gmail/Ollama calls.

No failures, uncertain criteria or new debt. D8 is checker-pass; phase is checked.
The checker changed only loop.md and verdicts.md, not implementation or
iterations.md. Earlier verdicts and human-accepted DEBT-001 remain in force.
D9/T044 remains pending: a human must run quickstart mailbox scenarios 1–6 and
3b, record timings in tests/golden/RESULTS.md, and sign off. Use
`/speckit-loop-status` to resume that manual gate. The loop remains open and
still requires `/speckit-loop-guard` plus human closure sign-off afterward.

Live OAuth, Gmail, Ollama, MCP Inspector/Claude Desktop, pipx installation and
minimum-Python execution were not checked. D9 real-mail accuracy/performance
is unverified; the accepted extraction injection risk remains.


## Post-iteration 23 manual gate independent check — 2026-10-14

This checker did not conduct or record the human mailbox run. D9 is the only
maker-ready criterion. The latest numbered maker iteration remains 23; commit
`dc6049b` adds the subsequent human validation report. One independent vote is
required. Checks ran against the clean feature tree at that commit.

### D9: pass (medium confidence)

- The current D9 criterion requires RESULTS.md records for Scenarios 1–6 and
  human sign-off. Scenario 3b timing/memory was explicitly excluded by the
  recorded human ruling in `d8cb227`; DEBT-002 retains that accepted gap.
- Inspected quickstart.md against the results table: setup and Scenarios 1–6
  are individually recorded as pass, on a real mailbox with qwen3:4b dated
  2026-10-14. Scenario 3b is explicitly marked not run, with no fabricated
  timing. debt.md names saurav-cgr's D9 sign-off and repeats the exclusion.
  T044 is checked. An independent document assertion verified all six rows,
  the waiver, accepted debt, sign-off and updated contract are consistent.
- Adversarial audit looked for missing scenarios, a claimed unmeasured timing,
  an absent sign-off, conflicting scope and implementation drift. None was
  found under the revised D9 contract. T044/quickstart retain the original 3b
  instructions; the explicit human ruling supersedes that part of the gate.
- Git comparison with previously checked `cbb3ce7` shows no source or executable
  test changes; only gate records and results changed. Full pytest still passes:
  460 tests in 4.52 seconds on Python 3.14.7. Ruff lint and format pass (43 files).
- This is verification of the required durable human report and sign-off,
  not independent reproduction of live runtime behavior. The maker's counts,
  permissions and no-body spot check were not used as independent evidence.
  Confidence is medium because the checker did not observe the human live run.

No failures, uncertain criteria or new debt under the revised contract. D9 is
checker-pass; phase remains checked. The checker edited only loop.md and
verdicts.md, not implementation, iterations.md, RESULTS.md or debt.md.
All automatable criteria now have checker passes; D4 remains human-signed with
accepted DEBT-001. Recommend `/speckit-loop-guard` for the required comprehension
checkpoint and explicit closure sign-off. The loop is not declared done.

Live Gmail/Ollama scenarios were not independently repeated. SC-001 speed and
memory remain unmeasured (accepted DEBT-002); the accepted prompt-injection
extraction leak remains (DEBT-001).

## Iteration 24 independent check — 2026-10-14

This checker did not produce iteration 24. D10 is the only maker-ready criterion;
D11–D15 remain pending. One independent vote is required. Checks ran in the clean
migration worktree `/Users/saurav/projects/applytrail-loop-iter-24`, on
`fastmcp-wip` at `468b84d`, rather than the feature branch's pre-migration tree.

### D10: pass (high confidence)

- Independent `uv sync` exits 0 and resolves 99 packages. No cyclopts warning
  appears on this run. The initial sandbox cache-access denial was resolved by
  rerunning with approved elevated access; it is not a dependency failure.
- Installed metadata prints `4.1.0 2.3.0` for fastmcp and mcp respectively.
- Adversarial assertions check both manifest and lock: fastmcp is a direct
  dependency, mcp is not, and the Python floor remains `>=3.11`. T045 is checked
  in the migration worktree's tasks.md. The commit diff changes only the
  dependency, lock and T045 checkbox; source and tests remain unchanged.
- Full pytest passes: 460 tests in 4.58 seconds. Ruff lint and format pass
  (43 files). These are compatibility checks, not evidence that D11 is complete:
  the server and client still use the transitive mcp package.

No failures, uncertain criteria or new debt. D10 becomes checker-pass and Phase
becomes checked. Only loop.md and verdicts.md are edited by this checker; the
implementation and iterations.md are untouched. Recommend `/speckit.loop.run`
for D11 and the remaining migration criteria. The loop is not done.

A fresh virtual environment, minimum-Python execution and live Gmail/Ollama were
not checked. D11–D15 remain unverified; the accepted DEBT-001 and DEBT-002 risks
remain. Direct receipt: verified the exact maker commit against D10 and recorded
V013 without expanding implementation scope.


## Iteration 25 independent check — 2026-10-14

This checker did not produce iteration 25. D11 is the only maker-ready criterion.
One independent vote is required. The primary source is the clean migration
worktree `/Users/saurav/projects/applytrail-loop-iter-24` on `fastmcp-wip`, commit
`3ac0041`. D12–D15 remain pending and were not graded.

### D11: pass (high confidence)

- Full pytest passes: 461 tests in 4.97 seconds. Ruff lint and format pass
  (43 files). Searches of src/tests find no direct mcp imports, MCPServer or
  StdioServerParameters. The server contains no CallToolResult construction.
- Reviewed the complete code/test diff against pre-goal-2 commit `3a091e5` and
  the callers in cli.py. Existing test expected values are unchanged. An AST
  comparison independently confirms every existing test assertion is preserved;
  the added StdioTransport assertion and the single masked-error test are the
  only additional assertions. T046–T050 are checked in worktree tasks.md.
- Independent adversarial probes reject six invalid/missing arguments before
  the service factory is reached. Four valid lower/upper-bound calls succeed,
  and their text JSON equals structured_content. All calls use fake Gmail.
- For both tools, injected AuthRequired, NetworkUnavailable, GmailRateLimited,
  GmailError(418), and an unexpected RuntimeError produce ten exact error
  responses. The unexpected error marker is absent from client responses;
  expected errors retain their contractual prefixes without SDK-added text.
- The real synchronous GmailMcp wrapper spawns the stdio server twice, using
  an explicitly passed empty temporary home whose path includes spaces.
  Both tools return typed AuthRequired errors in each session. Repeated context
  entry/exit clears client, portal and stack references; the home stays empty.
  No live Gmail or Ollama calls occur in this check.
- Replayed the two new assertions against source from `468b84d`, loaded only
  into disposable checker modules. The old client fails the StdioTransport
  assertion. The old server's unexpected-error response differs from the new
  exact masked text, so that assertion also fails. This independently proves
  the assertions discriminate the old implementation; it does not reconstruct
  the maker's historical order of edits.

No failures, uncertain criteria or new debt. D11 becomes checker-pass and Phase
becomes checked. Only loop.md and verdicts.md are edited by the checker; source,
tests, iterations.md and existing human records are untouched. DEBT-003's human
acknowledgement and D12 command approval remain recorded; D12 itself is pending.
Recommend `/speckit.loop.run` for the remaining migration criteria. Passing D11
is not loop closure.

FastMCP emits start/error logs on stderr during stdio calls; responses remain
parseable and the expected error text is preserved. D12 CLI schema/banner checks,
a fresh virtual environment, minimum-Python execution, and real-mail regression
were not run. Accepted DEBT-001 injection leakage and DEBT-002 unmeasured timing
remain. Direct receipt: verified D11 against the exact maker commit and recorded
V014 without modifying the implementation.


## Iteration 26 independent check — 2026-10-14

This checker did not produce iteration 26. D12 and D13 are the only maker-ready
criteria. One independent vote is required. The migration source is the clean
worktree `/Users/saurav/projects/applytrail-loop-iter-24`, `fastmcp-wip` at
`48dd4b1`. The constitution draft is deliberately checked in the main feature
working copy, as specified by the contract. D14 and D15 are not graded.

### D12: pass (high confidence)

- Ran the installed FastMCP CLI's list and call commands against the actual
  stdio server. Both commands explicitly set an empty temporary APPLYTRAIL_HOME
  inside --command, consistent with the approved DEBT-003 fix. The list command
  uses the same isolation safeguard; no credentials are loaded from the real home.
- List exits 0 and emits parseable JSON with exactly search_job_emails and
  get_email. Independent assertions verify required arguments, datetime format,
  nullable page_token, integer bounds/defaults (1–500/500 and 500–20000/4000),
  search output keys and message fields, and all seven email output fields with
  boolean truncated. These match contracts/mcp-tools.md.
- The search call with after=2026-04-15T00:00:00Z exits 1 and stdout is exactly
  `Error: AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth.`
  Neither stdout nor stderr contains a FastMCP version banner, banner marker or
  banner frame. The isolated home remains empty. Stderr contains ordinary
  server logs; it does not contaminate the JSON or error text on stdout.
- Repeated the CLI check with schema assertions after inspecting the primary
  JSON. Both runs passed. No README real-home call or live Gmail/Ollama call ran.

### D13: pass (high confidence)

- AGENTS.md names FastMCP 4.x server/client and StdioTransport, with mcp as its
  protocol layer. README adds the FastMCP CLI inspector option and explicitly
  explains passing APPLYTRAIL_HOME inside --command. Existing MCP Inspector
  and Claude Desktop snippets remain unchanged.
- Every task T045–T053 is checked in the migration worktree. Its latest commit
  changes only AGENTS.md, README.md and task checkboxes. Source, tests, manifest
  and lock have no drift from independently checked commit 3ac0041.
- The main-copy constitution footer changes 1.1.0 to 1.1.1, its new Sync Impact
  Report describes that PATCH, and Technical Constraints name fastmcp 4.x.
  An independent comparison confirms all Core Principles are unchanged.
  The constitution diff remains unstaged and uncommitted, as required.
- Ruff lint and format pass (43 files). Full pytest also passes: 461 tests in
  5.65 seconds on the exact migration tree.

No failures, uncertain criteria or new debt. D12 and D13 become checker-pass;
Phase becomes checked. Only loop.md and verdicts.md are edited by this checker;
implementation, iterations.md, constitution and human sign-off records are
untouched. Recommend `/speckit.loop.run` for the remaining D14/D15 work.
The checker does not declare the migration done.

Real-mail regression (D14), final single-commit landing (D15), minimum-Python
execution and fresh-environment installation remain unchecked. Accepted
DEBT-001 injection leakage and DEBT-002 unmeasured timing remain. Direct receipt:
verified CLI parity and documentation/governance at their primary sources and
recorded V015/V016 without expanding implementation scope.


## Iteration 27 independent check — 2026-10-14

This checker did not produce iteration 27. D15 is the only maker-ready criterion.
One independent vote is required. Primary source: feature branch
`001-gmail-sync-table` at `1e8fbc53ff632721d9fcc7aa3de1212cd407781c`.
D14 remains pending and is not graded; no human real-mail regression report or
sign-off for this migration exists in debt.md.

### D15: pass (high confidence)

- Independent history assertions confirm HEAD is 1e8fbc5 on the required
  feature branch, its parent is pre-migration 3a091e5, and exactly one commit
  exists in that range. Its subject is
  `refactor(mcp): migrate MCP server and client to FastMCP`.
- The full committed tree hash equals independently checked 48dd4b1 and
  backup/pre-squash-fastmcp. Squashing introduced no content change.
- The commit changes exactly the nine intended files: AGENTS.md, README.md,
  pyproject.toml, uv.lock, both MCP modules, both MCP test files and tasks.md.
  T045–T053 are checked; T054 stays open. The constitution is excluded from
  the commit and remains an unstaged, uncommitted draft for human review.
- Adversarial audit checks for extra commits/files, a changed reviewed tree,
  missing task checkboxes, accidental constitution inclusion and uncommitted
  implementation drift. None is found. Current uncommitted loop, quickstart
  and constitution documents do not change the tested executable tree.
- Ran the complete suite on that exact feature implementation: 461 tests pass
  in 5.78 seconds. Ruff lint and format pass (43 files).

No failures, uncertain targeted criteria or new debt. D15 becomes checker-pass
and Phase becomes checked. Only loop.md and verdicts.md are edited by this
checker; the implementation, iterations.md, constitution and human records are
untouched. No commit or push was made.

Recommend `/speckit.loop.status` until the human runs `applytrail` and
`applytrail --offline` on the real mailbox and records the D14 regression
report/sign-off. T054 and D14 remain pending. After that gate receives its own
checker verdict, `/speckit.loop.guard` is still required for migration closure.
The earlier goal-1 closure sign-off does not close goal 2.

Live Gmail/Ollama, minimum-Python execution and fresh-environment installation
were not checked. Accepted DEBT-001 injection leakage and DEBT-002 unmeasured
timing remain. Direct receipt: verified the single landed commit and its tested
tree against D15 without expanding implementation scope.
