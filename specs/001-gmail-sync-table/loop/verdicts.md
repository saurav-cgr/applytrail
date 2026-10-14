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
