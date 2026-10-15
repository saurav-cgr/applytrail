# Contract: Local Store File (changes)

Extends [001 contracts/store-schema.md](../../001-gmail-sync-table/contracts/store-schema.md).
Path, encoding, atomic write, file modes, and `schema_version: 1` are unchanged.

One optional field is added under `sync`:

```json
"sync": {
  "checkpoint": "2026-10-12T14:03:00Z",
  "mailbox": "me+jobs@example.com",
  "...": "other fields unchanged"
}
```

- Missing or `null`: links fall back to `u/0`. Stores written before this feature load unchanged.
- The guarantee that saving the same state twice gives byte-identical files still holds: the
  mailbox is the same on each run unless the user signs in with a different account.
- Validation failure (for example no `@`): the store refuses to load, like any other invalid field.
