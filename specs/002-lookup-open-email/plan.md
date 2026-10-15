# Implementation Plan: Application Lookup and Email Opening

**Branch**: `002-lookup-open-email` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-lookup-open-email/spec.md`

## Summary

Add two offline subcommands to the CLI. `applytrail check NAME` answers "did I already apply?"
by matching company names against the local store (with the existing company normalization and
word-prefix matching), and suggests close spellings when there's no match. `applytrail open
TARGET [--print]` opens an application's latest Gmail thread by row number or company name, and
always prints the address. The table gains a `#` row-number column within the 100-column budget.
Thread links target the synced mailbox, using an address that a new read-only MCP tool,
`get_account`, detects once per sync and saves in the store. Stdlib only (`difflib`, `webbrowser`,
`urllib.parse`). No new dependency, per the user's instruction.

## Technical Context

**Language/Version**: Python ≥ 3.11 (unchanged)

**Primary Dependencies**: existing set only (`fastmcp` 4.x, `google-api-python-client`,
`google-auth-oauthlib`, `pydantic` v2, `rich`, `python-dotenv`). New stdlib modules used:
`difflib`, `webbrowser`, `urllib.parse`.

**Storage**: existing JSON store. One optional field added, `sync.mailbox`. `schema_version`
stays 1 ([contracts/store-schema.md](contracts/store-schema.md)).

**Testing**: `pytest` with anonymized fixtures, no Gmail and no live model. Browser launch is
monkeypatched.

**Target Platform**: macOS and Linux terminals, including SSH sessions with no display.

**Project Type**: CLI, plus a stdio MCP server.

**Performance Goals**: `check` and `open` under 1 s for 500 applications (SC-002). Sync gains one
`getProfile` call per run, which is negligible against the 60 s / 20 emails target.

**Constraints**: offline for `check`/`open`. Table ≤ 100 columns. No colour-only signals. Expected
failures print one line and exit non-zero. Email-derived text is never parsed as markup.

**Scale/Scope**: up to about 1,000 applications in one store (the row-number column is sized for
3 digits). Two new modules (`lookup.py`, `links.py`) and edits to `cli.py`, `render.py`,
`models.py`, `sync.py`, `mcp_server.py`, `mcp_client.py`, `gmail_client.py`.

No NEEDS CLARIFICATION items remain. All are resolved in [research.md](research.md) R1–R10.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Result |
|---|---|---|
| I. Least-privilege, read-only | New tool `get_account` is read-only (`users.getProfile`), covered by `gmail.readonly`. No new scope, no write tool, so no amendment is needed. | PASS |
| II. Email is untrusted | No LLM change. The address is built only from Gmail IDs plus the account address, both percent-encoded (R8). Company, role and lookup text are printed as plain `Text` (R10). Nothing from email is executed or fetched: `webbrowser` opens a `mail.google.com` URL built from Gmail identifiers. | PASS |
| III. Deterministic core | Lookup, suggestions, numbering and URL building are plain code. No model involved. | PASS |
| IV. Local-first, idempotent | `check`/`open` never write. Sync writes `mailbox` with an atomic save. The same account gives a byte-identical store, so the "no new mail changes nothing" guarantee holds. | PASS |
| V. Privacy | The mailbox address lives only in the 0600 store. It's never logged, and never in error text or the debug log (which already omits messages). No email bodies are touched. | PASS |
| VI. Clean MCP contract | `get_account` is typed, has a docstring, and uses the same error prefixes. It's usable from MCP Inspector and Claude Desktop. No stdout outside the protocol. | PASS |
| VII. Terminal UX | `#` column keeps 100 columns (R6). Row numbers and statuses are text. One-line actionable errors with documented exit codes (R2). Company hyperlinks are kept and now target the right account. | PASS |
| VIII. Test-first | Tests for lookup (matching, normalization, suggestions), render (column, width, link) and store/model (`mailbox`) are written and seen failing before implementation. Labelled lists cover SC-003 and SC-003a. | PASS |
| IX. Simplicity | Stdlib only, no new dependency. Provider code is untouched (`extractor.py` doesn't change). No web UI or database. | PASS |

**Post-design re-check (after Phase 1)**: PASS. The design adds no scope or dependency and no
write path. Follow-up for the polish step: AGENTS.md rule 1 lists the MCP tools by name
(`search_job_emails`, `get_email`), so it must add `get_account`. The constitution itself names no
tools and needs no amendment.

## Project Structure

### Documentation (this feature)

```text
specs/002-lookup-open-email/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R10
├── data-model.md        # Phase 1: SyncState.mailbox, in-memory lookup types
├── quickstart.md        # Phase 1: validation scenarios Q1–Q7
├── contracts/
│   ├── cli.md           # check / open subcommands, table change, exit codes
│   ├── mcp-tools.md     # get_account tool
│   └── store-schema.md  # sync.mailbox
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 ($speckit-tasks, not created here)
```

### Source Code (repository root)

```text
src/applytrail/
├── cli.py            # + subparsers: check, open (--print); exit codes 2/6
├── lookup.py         # NEW: numbered(), find(), suggest(), lookup normalization
├── links.py          # NEW: thread_url(), can_launch_browser(), open_in_browser()
├── render.py         # + "#" column, narrower Company/Role, link via links.thread_url,
│                     #   build_table(rows=…) for subsets, not-found/suggestion lines
├── models.py         # + SyncState.mailbox, AccountInfo
├── sync.py           # + MailSource.get_account(); set store.sync.mailbox at run start
├── mcp_server.py     # + get_account tool
├── mcp_client.py     # + GmailMcp.get_account()
└── gmail_client.py   # + get_account(service) via users().getProfile

tests/
├── fakes.py                         # + fake get_account
├── fixtures/store_lookup.json       # NEW: anonymized store for lookup/open/quickstart
├── unit/test_lookup.py              # NEW
├── unit/test_links.py               # NEW
├── unit/test_render.py              # + # column, width ≤ 100, mailbox link, literal markup
├── unit/test_cli.py                 # + check/open exit codes and output
├── unit/test_models.py              # + mailbox validation, old store loads
├── unit/test_gmail_client.py        # + getProfile mapping and errors
├── contract/test_mcp_tools.py       # + get_account contract
└── integration/test_sync_*.py       # + mailbox saved and replaced
```

**Structure Decision**: Single project, existing `src/` layout. Matching and suggestions go in
`lookup.py` so `render.py` stays presentation-only. Address and browser handling go in `links.py`
so the table and `open` share one address builder.

## Delivery order (input for `/speckit-tasks`)

- **Foundation**: `lookup.numbered()`, the `#` column, `links.thread_url(thread_id, mailbox=None)`
  with the `u/0` fallback, and CLI subparser scaffolding. The table must look right before any
  story depends on it.
- **US1 (P1)**: `lookup.find()` and `suggest()`, `check` subcommand, exit codes 0/2/6.
  Independently shippable.
- **US2 (P2)**: `open` subcommand (by number or name, `--print`), browser decision. Links still
  use `u/0`.
- **US3 (P3)**: `SyncState.mailbox`, `get_account` end to end (gmail_client → server → client →
  sync), and the table link plus `open` passing the mailbox to `links.thread_url`.
- **Polish**: README (check, open, `--print`, row numbers after sync, exit codes, multi-account
  note), AGENTS.md tool list, quickstart Q6 manual result.

## Complexity Tracking

No constitution violations. Nothing to justify.
