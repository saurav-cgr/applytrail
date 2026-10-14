# Data Model: Gmail Sync and Application Table

**Feature**: `001-gmail-sync-table` | **Date**: 2026-10-14

All entities are Pydantic models in `src/applytrail/models.py`. All timestamps are timezone-aware
UTC. The whole store is serialized as one JSON document (see
[contracts/store-schema.md](contracts/store-schema.md)).

## Status (enum)

`applied`, `in_review`, `assessment`, `interview`, `offer`, `rejected`, `withdrawn`.

Display labels: Applied, In Review, Assessment, Interview, Offer, Rejected, Withdrawn.

No ordering is enforced between statuses: the newest email wins (spec Assumptions). The only
guard is chronological: an email dated before `Application.last_activity` never changes status.

## Extraction (LLM output, not stored as-is)

| Field | Type | Rules |
|---|---|---|
| `is_job_application` | bool | `false` means not about the user's own application |
| `company` | str | Trimmed; empty means unusable |
| `role` | str \| null | Trimmed; empty string becomes null |
| `status` | Status \| `"unknown"` | `"unknown"` means unusable |
| `evidence` | str | ≤ 200 chars (validation bound); prompt asks for ≤ 120; short quote supporting the status |

Outcome per email (deterministic, in `sync.py`):

- schema validation fails → `skipped` (reason `invalid_output`)
- `is_job_application == false` → `ignored`
- empty `company` or `status == "unknown"` → `skipped` (reason `incomplete`)
- otherwise → `applied` to an Application via merge rules below

## EmailMeta (from MCP `get_email`, not stored as-is)

`message_id`, `thread_id`, `date` (from the `Date` header, fallback Gmail `internalDate`),
`sender`, `subject`, `body_text` (truncated by the server to `max_chars`).

## Application (stored)

| Field | Type | Rules |
|---|---|---|
| `key` | str | `company_key + "|" + role_key`; unique; `role_key` is `""` when role unknown |
| `company` | str | Display spelling from the most recent applied email |
| `role` | str \| null | Display spelling; null shows as "Unknown" |
| `status` | Status | |
| `last_activity` | datetime | Date of newest applied email |
| `first_seen` | datetime | Date of oldest applied email |
| `thread_id` | str | Thread of newest applied email (used for the Gmail link) |
| `subject` | str | Subject of newest applied email, ≤ 200 chars |
| `evidence` | str | From newest applied email, ≤ 200 chars |
| `message_ids` | list[str] | All contributing message IDs, in order applied |

Never stored: email body, sender address beyond what is in `subject`/`evidence`.

## ProcessedEmail (stored)

| Field | Type | Rules |
|---|---|---|
| `message_id` | str | Unique key |
| `date` | datetime | Email date |
| `outcome` | `applied` \| `ignored` \| `skipped` | |
| `reason` | str \| null | For `skipped`: `invalid_output`, `incomplete` |
| `application_key` | str \| null | Set when `applied` |

## SyncState (stored)

| Field | Type | Rules |
|---|---|---|
| `checkpoint` | datetime \| null | Null before the first completed sync |
| `last_sync_at` | datetime \| null | When the latest sync run finished (complete or partial) |
| `last_sync_complete` | bool | False if the latest run stopped early (Ctrl-C, Ollama failure, network) |
| `stop_reason` | `complete` \| `provider_unavailable` \| `network` \| `interrupted` \| null | Why the latest run ended; null before the first run |
| `pending` | int | Candidate emails left unprocessed when the latest run stopped; 0 when complete |
| `added` | list[str] | Application keys first created in the latest run (`NEW`) |
| `updated` | list[str] | Application keys changed (not created) in the latest run (`UPD`) |
| `last_run_counts` | {read, added, updated, ignored, skipped} | For the summary line |

`stop_reason` and `pending` exist only to build messages (default command and
`--offline`). They never affect what gets fetched: resuming relies only on `checkpoint` plus
`processed`.

`added` and `updated` are reset at the start of every sync run, including runs that find nothing
(spec US2 scenario 3). `--offline` reads them without changing them.

## Store (root)

`schema_version: 1`, `applications: dict[key, Application]`,
`processed: dict[message_id, ProcessedEmail]`, `sync: SyncState`.

## Merge rules (`merge.py`)

Input: usable Extraction + EmailMeta. Let `ck = norm_company(company)`, `rk = norm_role(role)`.

1. **Role given** (`rk != ""`):
   - If `ck|rk` exists, target it.
   - Else if the company has exactly one application and its role is unknown (`ck|`), target it
     and fill in the role (re-key to `ck|rk`).
   - Else create `ck|rk`.
2. **Role missing** (`rk == ""`):
   - If the company has exactly one application, target it.
   - Else if `ck|` exists, target it.
   - Else create `ck|`.
3. **Apply to target**:
   - Always: append `message_id`; set `first_seen = min(first_seen, date)`.
   - If `date >= last_activity`: set `status`, `last_activity`, `thread_id`, `subject`,
     `evidence`, display `company`; set `role` if it was null.
   - If `date < last_activity`: no status or display change (FR-009).
4. **Badges**: created in this run → `added`. Otherwise, if `status`, `role`, or `last_activity`
   differs from its value at the start of the run → `updated` (and not in `added`).

## State transitions (Application.status)

Any status → any status, driven only by a newer email. Creation sets the initial status from the
first applied email.

## Ordering (render)

`last_activity` descending, then `company` ascending (casefolded), then `role`.
