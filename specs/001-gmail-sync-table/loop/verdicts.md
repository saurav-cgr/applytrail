# Checker Verdicts

A criterion is `pass` only after the checker confirmed it against the PRIMARY
source (a run, a file, an endpoint), not the maker's self-assessment.

| ID | Iteration | Criterion | Method (primary source) | Verdict | Confidence | Date |
|----|-----------|-----------|-------------------------|---------|------------|------|
| V001 | 2 | D1 | Independent `uv sync` (exit 0), targeted pytest (68 passed), full pytest (101 passed), Ruff lint/format (exit 0); source and task audit; adversarial probes below violate T007/T012 and the store contract | fail | high | 2026-10-14 |
| V002 | 2 | D2 | `git log --oneline -8`, `git show --stat 68e21e2`: one foundation commit, 34 files confined to T001–T014; `git diff 68e21e2 HEAD -- src tests pyproject.toml uv.lock specs/001-gmail-sync-table/tasks.md` empty | pass | high | 2026-10-14 |
| V003 | 3 | D1 | Independent uv sync exit 0; targeted pytest 82 passed; full pytest 115 passed; Ruff lint/format exit 0; source/task audit and disposable-directory schema, completion, corrupt-destination, temporary-symlink/failed-rename probes | pass | high | 2026-10-14 |
| V004 | 3 | D2 | git log and git show --stat 7818ce5: exactly one foundation commit, 34 Phase 1–2 files; git diff 7818ce5 HEAD -- src tests pyproject.toml uv.lock specs/001-gmail-sync-table/tasks.md empty | pass | high | 2026-10-14 |

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
