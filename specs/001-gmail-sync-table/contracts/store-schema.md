# Contract: Local Store File

Path: `$APPLYTRAIL_HOME/applications.json` (default `~/.applytrail/applications.json`).
Encoding: UTF-8 JSON, 2-space indent, keys sorted. Field definitions: [../data-model.md](../data-model.md).

```json
{
  "schema_version": 1,
  "applications": {
    "acme|backend engineer": {
      "key": "acme|backend engineer",
      "company": "Acme Inc.",
      "role": "Backend Engineer",
      "status": "interview",
      "last_activity": "2026-10-12T14:03:00Z",
      "first_seen": "2026-09-30T08:11:00Z",
      "thread_id": "18c0aa…",
      "subject": "Interview invitation – Backend Engineer",
      "evidence": "We'd like to invite you to a technical interview",
      "message_ids": ["18b9…", "18c1…"]
    }
  },
  "processed": {
    "18c1…": {
      "message_id": "18c1…",
      "date": "2026-10-12T14:03:00Z",
      "outcome": "applied",
      "reason": null,
      "application_key": "acme|backend engineer"
    }
  },
  "sync": {
    "checkpoint": "2026-10-12T14:03:00Z",
    "last_sync_at": "2026-10-14T08:02:11Z",
    "last_sync_complete": true,
    "stop_reason": "complete",
    "pending": 0,
    "added": [],
    "updated": ["acme|backend engineer"],
    "last_run_counts": {"read": 3, "added": 0, "updated": 1, "ignored": 2, "skipped": 0}
  }
}
```

## Guarantees

- Written atomically: temp file in the same directory, `fsync`, `os.replace`.
- Directory mode 0700; file mode 0600.
- Contains no email bodies.
- Unknown `schema_version` or validation failure: the tool refuses to load and refuses to write.
- Saving the same logical state twice produces byte-identical files (sorted keys), so "no change"
  is verifiable by checksum (SC-004), except `sync.last_sync_at`, which records each run.
