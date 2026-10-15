# Contract: Command-Line Interface (changes)

Extends [001 contracts/cli.md](../../001-gmail-sync-table/contracts/cli.md). Everything not listed
here is unchanged.

```text
applytrail [--offline] [--version] [--help]
applytrail check NAME...
applytrail open TARGET... [--print]
```

`check` and `open` read only the local store. They start no MCP server, contact neither Gmail nor
Ollama, and never write the store.

## Table layout (changed)

| Column | Width | Content |
|---|---|---|
| `#` | digits of row count (3 for ≤ 999 rows) | Row number, right-aligned |
| (badge) | 4 | `NEW`, `UPD`, or blank |
| Company | ≤ 25 | Ellipsized; hyperlink to `links.thread_url` where supported |
| Role | ≤ 27 | Ellipsized; `Unknown` when null |
| Status | 12 | Display label |
| Last seen | 10 | `YYYY-MM-DD` local time |

Total ≤ 100 columns including borders. Row numbers are 1-based in newest-first order and may change
after a sync. `check` and `open` (several matches) use a variant with a `First seen` column; see
below.

## `applytrail check NAME...`

Arguments are joined with single spaces. Matching: research R3.

**Found** (exit 0), stdout:

```text
Found 2 applications matching "acme":
┌───┬────────────┬───────────┬──────────────────┬───────────┬────────────┐
│ # │ First seen │ Company   │ Role             │ Status    │ Last seen  │
├───┼────────────┼───────────┼──────────────────┼───────────┼────────────┤
│ 1 │ 2026-09-30 │ Acme Inc. │ Backend Engineer │ Interview │ 2026-10-12 │
│ 5 │ 2026-08-20 │ Acme Inc. │ Data Engineer    │ Rejected  │ 2026-09-02 │
└───┴────────────┴───────────┴──────────────────┴───────────┴────────────┘
```

With a column header row. "application" is singular for one match. The quoted text is what the
user typed, printed literally.

The `check` table differs from the main table (FR-004): the badge column is replaced by
`First seen`, and Role narrows so the total stays ≤ 100 columns.

| Column | Width | Content |
|---|---|---|
| `#` | digits of row count | Row number from the main table |
| First seen | 10 | `YYYY-MM-DD` local time (`first_seen`) |
| Company | ≤ 25 | Ellipsized; hyperlink as in the main table |
| Role | ≤ 21 | Ellipsized; `Unknown` when null |
| Status | 12 | Display label |
| Last seen | 10 | `YYYY-MM-DD` local time |

`open` with several matches uses this same `check` table.

**Not found** (exit 6), stdout:

```text
No application found for "Gogle".
Did you mean: Google (#4), Goggle Labs (#12)?
Last sync: 2026-10-14 08:02 (complete)
```

- The `Did you mean` line appears only when suggestions exist (research R4). A company with several
  applications lists every number: `Acme Inc. (#1, #7)`.
- The `Last sync` line reuses the `--offline` footer text, including the incomplete wording.

**Errors**

| Code | Condition | Message (stderr, one line) |
|---|---|---|
| 2 | Name empty or only punctuation | `Enter a company name, for example: applytrail check acme` |
| 6 | No data yet (no applications, no sync) | `No data yet. Run applytrail to sync.` |
| 5 | Store unreadable | existing message |

## `applytrail open TARGET... [--print]`

- A single all-digit argument is a row number. Anything else is joined as a company name and matched
  as for `check`.
- `--print`: print the address and don't launch a browser.

**One application resolved** (exit 0), stdout:

```text
Opening Acme Inc. — Backend Engineer (#1)
https://mail.google.com/mail/u/me%2Bjobs@example.com/#all/18c0aa…
```

The first word is `Address for` instead of `Opening` when `--print` is given or no graphical session
is detected (research R9). Role `null` prints as `Unknown`. The address is on its own line with no
inserted line breaks. If the browser launch fails, stderr gets
`Could not open a browser; use the address above.` and the exit code is still 0.

**Several matches by name** (exit 2): the matching rows are printed as a table on stdout, then
stderr gets `Several applications match "acme". Run: applytrail open <number>`. Nothing is opened.

**Errors**

| Code | Condition | Message (stderr, one line) |
|---|---|---|
| 2 | Row number out of range | `No row 42. Choose a number from 1 to 10 (see applytrail --offline).` |
| 2 | Name empty or only punctuation | `Enter a row number or company name, for example: applytrail open 3` |
| 6 | No company match | The not-found output of `check` on stdout (with suggestions and Last sync) |
| 6 | No data yet | `No data yet. Run applytrail to sync.` |
| 5 | Store unreadable | existing message |

## Exit code summary (additions)

| Code | Meaning |
|---|---|
| 0 | `check`: found. `open`: address printed |
| 2 | `check`/`open`: input needs fixing (empty name, bad row number, several matches) |
| 6 | `check`/`open`: no matching application, or no data yet |

No new environment variables.
