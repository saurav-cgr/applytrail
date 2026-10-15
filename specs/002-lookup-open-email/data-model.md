# Data Model: Application Lookup and Email Opening

**Feature**: `002-lookup-open-email` | **Date**: 2026-10-15

Extends [001 data model](../001-gmail-sync-table/data-model.md). Only the changes and new
in-memory types are listed here.

## SyncState (stored) — one new field

| Field | Type | Rules |
|---|---|---|
| `mailbox` | str \| null | Address of the synced Gmail account, from MCP `get_account`. Set at the start of every sync run, before searching, and replaced if it changed. Null until the first sync after this feature ships. Validation: 3–254 characters, exactly one `@`, no whitespace or control characters. |

- Not reset with `added`/`updated`: it describes the mailbox, not the run.
- `--offline`, `check` and `open` read it and never change it.
- Never logged, and never included in error messages or the debug log.
- `schema_version` stays `1`. The field is optional with a default of null, so stores written
  before this feature still load. Older ApplyTrail builds ignore the field (Pydantic ignores
  unknown keys) and drop it when they next save. The next sync with this feature writes it again.

## AccountInfo (MCP `get_account` output, not stored as-is)

| Field | Type | Rules |
|---|---|---|
| `email_address` | str | Same validation as `SyncState.mailbox` |

## NumberedApplication (in memory, never stored)

| Field | Type | Rules |
|---|---|---|
| `number` | int ≥ 1 | 1-based position in the `render.sort_key` order of the current store |
| `app` | Application | Unchanged |

Produced only by `lookup.numbered(store)`. The table, `check` and `open` all use it (FR-010).

## LookupResult (in memory, never stored)

| Field | Type | Rules |
|---|---|---|
| `query` | str | Normalized lookup text (research R3), non-empty |
| `matches` | list[NumberedApplication] | Newest activity first (same order as the table) |
| `suggestions` | list[Suggestion] | Empty when `matches` is not empty; at most 3 |

`found` ⇔ `matches` is not empty.

## Suggestion (in memory, never stored)

| Field | Type | Rules |
|---|---|---|
| `company` | str | Display company of the newest application with this normalized company |
| `numbers` | list[int] | Row numbers of all applications with this normalized company, ascending |
| `score` | float | Similarity score 0.75–1.0 (research R4); sort key only, never shown |

Order: `score` descending, then `company` casefolded ascending.

## Thread address (derived, never stored)

`links.thread_url(app.thread_id, store.sync.mailbox)` → see [research R8](research.md#r8-gmail-thread-address).
Inputs are Gmail identifiers only.
