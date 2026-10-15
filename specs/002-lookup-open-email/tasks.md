---

description: "Task list for 002-lookup-open-email"
---

# Tasks: Application Lookup and Email Opening

**Input**: Design documents from `specs/002-lookup-open-email/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli.md, mcp-tools.md,
store-schema.md), quickstart.md

**Tests**: Required. The user asked for tests before implementation for render and query
(lookup), and AGENTS.md rule 8 requires test-first for render, store and normalize code. Every test
task must be run and **seen failing** before its implementation task starts. Tests use anonymized
fixtures and never call Gmail, Ollama, or a real browser.

**Organization**: Setup → Foundational → US1 (P1) → US2 (P2) → US3 (P3) → Polish. Each story ends
with a ruff + pytest gate and its own Conventional Commit. Setup/foundation and polish get their
own commits (AGENTS.md). Work on branch `002-lookup-open-email`. Do not push.

**No golden-set eval is needed**: this feature doesn't touch the extraction prompt, schema, or
model.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 (spec.md user stories)

---

## Phase 1: Setup

**Purpose**: Baseline and shared test data

- [x] T001 Confirm the current branch is `002-lookup-open-email` and the baseline is green from the repository root: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. Note the passing test count for comparison.
- [x] T002 [P] Create anonymized store fixture `tests/fixtures/store_lookup.json`. It must be a valid `schema_version: 1` store (shape per specs/001-gmail-sync-table/contracts/store-schema.md) with **no** `sync.mailbox` key, `sync.last_sync_at` = `2026-10-14T08:02:11Z`, `last_sync_complete: true`, `stop_reason: "complete"`, and these applications (hex `thread_id`s such as `18c0aa01`). Newest-first order gives the row numbers in brackets:
  - [1] `Acme Inc.` / `Backend Engineer` / interview / last 2026-10-12, key `acme|backend engineer`
  - [2] `Google` / `Software Engineer` / in_review / 2026-10-10
  - [3] `Globex International` / null role / applied / 2026-10-05, key `globex international|`
  - [4] `[bold]Evil[/bold]` / `Engineer` / applied / 2026-09-20
  - [5] `Acme Inc.` / `Data Engineer` / rejected / 2026-09-02
  - [6] `Northwind Traders` / `Analyst` / withdrawn / 2026-08-15
  - [7] `Brightwave Labs` / `QA Engineer` / offer / 2026-08-01

  Leave `processed` empty or minimal. Don't include Initech, Gogle, or any real person's data.
- [x] T003 [P] Add `load_store_fixture(name: str) -> Store` to `tests/fakes.py`. It reads `tests/fixtures/<name>` and returns `Store.model_validate(...)`. Add a test in `tests/unit/test_fakes.py` that `store_lookup.json` loads with 7 applications.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Row numbers (research R5), the `#` column (R6), and one shared thread-address builder (R8, `u/0` only for now). All three stories depend on these.

**⚠️ No user story work starts until this phase is green and committed.**

### Tests first (write, run, see them fail)

- [x] T004 [P] Create `tests/unit/test_lookup.py` with failing tests for `lookup.numbered(store) -> list[NumberedApplication]`: numbers are 1-based and follow `render.sort_key` (newest `last_activity` first, then company, then role, casefolded); ties keep that order; an empty store gives `[]`; on `store_lookup.json` the numbers match T002's bracketed list. `NumberedApplication` has fields `number: int` (≥ 1) and `app: Application`.
- [x] T005 [P] Create `tests/unit/test_links.py` with failing tests for `links.thread_url(thread_id, mailbox=None)`. `thread_url("18c2f0a1b2")` must equal `https://mail.google.com/mail/u/0/#all/18c2f0a1b2`, and the thread id is percent-encoded with `quote(thread_id, safe="")` (for example, `a/b#c` must not leak `/` or `#`).
- [x] T006 [P] Update `tests/unit/test_render.py` before touching `render.py`:
  - `test_columns_in_order` expects `["#", "", "Company", "Role", "Status", "Last seen"]`.
  - `test_column_widths` expects Company ≤ 25, Role ≤ 27, Status 12, Last seen 10, badge 4, and `#` as wide as the digits of the row count.
  - `test_long_names_are_ellipsized_within_100_columns` asserts company ≤ 25 and role ≤ 27.
  - New test: 999 rows with maximum-length names render with every line ≤ 100 columns and no wrapped rows.
  - New test: row numbers appear as plain text, right-aligned.
  - New test: `build_table(store, rows=subset)` renders only the subset, keeping the original numbers.
  - New test: a company named `[bold]Evil[/bold]` prints literally.
  - `test_company_links_to_the_gmail_thread` still expects `u/0`.

### Implementation

- [x] T007 Create `src/applytrail/lookup.py` with a module docstring citing research R3–R5, a frozen dataclass `NumberedApplication(number: int, app: Application)`, and `numbered(store: Store) -> list[NumberedApplication]` built from `sorted(store.applications.values(), key=render.sort_key)`. Make T004 pass. Move `sort_key` into `lookup.py` and re-export it from `render.py` if that's needed to avoid an import cycle.
- [x] T008 [P] Create `src/applytrail/links.py` with `GMAIL_THREAD_URL_TEMPLATE` and `thread_url(thread_id: str, mailbox: str | None = None) -> str`. With `mailbox=None` it uses `u/0`. Make T005 pass.
- [x] T009 Update `src/applytrail/render.py` to make T006 pass:
  - Add a first column `#` (right-aligned, `no_wrap`, width = digits of the row count) and narrow Company to `max_width=25` and Role to `max_width=27`.
  - Change `build_table(store, rows: list[NumberedApplication] | None = None)` to default to `lookup.numbered(store)`.
  - Build the Company link with `links.thread_url(app.thread_id)` and delete `GMAIL_THREAD_URL`. Grep `src/` and `tests/` for other uses of it.
- [x] T010 Update the table layout section of `README.md` if it describes columns (add the `#` column). Otherwise leave it for polish. (Skipped per loop memory M-006 A1: T046 covers the README.)
- [ ] T011 Gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest` must all pass. Then commit `feat(table): add row-number column and shared thread link builder` (Conventional Commit, foundation).

**Checkpoint**: The table shows row numbers within 100 columns, and existing behaviour is unchanged.

---

## Phase 3: User Story 1 - Check whether I already applied (Priority: P1) 🎯 MVP

**Goal**: `applytrail check NAME...` answers found / not found from the saved store, with close-spelling suggestions (FR-001 to FR-008, FR-005a, FR-018, FR-019).

**Independent Test**: With `store_lookup.json`: `check acme` lists rows 1 and 5 and exits 0; `check Initech` says not found, prints the Last sync line, and exits 6; `check Gogle` suggests `Google (#2)` and exits 6; `check "&"` exits 2. Gmail and Ollama are never contacted, and the store file is byte-identical afterwards.

### Tests first (write, run, see them fail)

- [ ] T012 [P] [US1] Add failing tests to `tests/unit/test_lookup.py` for query normalization and matching (research R3):
  - `normalize_query(text) -> list[str]` is `norm_company(text).split()` with one trailing `"and"` word dropped. `"Acme & Co"` → `["acme"]`. `""`, `"   "` and `"&"` → `[]`.
  - `find(store, text)` raises `InvalidInput` when `normalize_query` gives `[]`.
  - Found cases: `acme`, `ACME`, `Acme, Inc.`, `acme corp` and `Acme & Co` each return rows [1, 5] in that order. `glob`, `globex` and `international` return row [3].
  - Not-found cases: `lob`, `engineer` (role-only text), and `Initech` return no matches.
  - Rejected and withdrawn applications are found.
  - An application whose display company differs from its key's company part matches either spelling.
  - `LookupResult` fields are `query: str`, `matches: list[NumberedApplication]` and `suggestions: list[Suggestion]`. `found` is true exactly when `matches` is non-empty.
- [ ] T013 [US1] Add failing suggestion tests to `tests/unit/test_lookup.py` (research R4; depends on T012, same file):
  - `Gogle` → first suggestion `Google` with `numbers == [2]`.
  - A company with several applications lists all its numbers ascending: `Acmee` → `Acme Inc.` with `[1, 5]`.
  - At most 3 suggestions, ordered by score descending and then by casefolded company ascending.
  - Suggestions are empty whenever `matches` is non-empty, and empty when nothing scores ≥ `SUGGEST_CUTOFF = 0.75`.
  - Results are identical across repeated calls.
  - **SC-003** labelled list: at least 20 spelling variants (case, punctuation, legal suffixes, partial names) of fixture companies are all found, and 10 unrelated names (for example `Initech`, `Umbrella`, `Stark Industries`) produce no match.
  - **SC-003a** labelled list: at least 10 one- or two-letter typos of fixture companies. The intended company appears in the suggestions for at least 90% of them.
- [ ] T014 [P] [US1] Add failing render tests to `tests/unit/test_render.py` for `render_found(result, store, console)` and `render_not_found(result, store, console)` (contracts/cli.md `check`):
  - Header `Found 2 applications matching "acme":`, singular `application` for one match, then the `check` table of matched rows with original numbers. Its columns are `["#", "First seen", "Company", "Role", "Status", "Last seen"]` (no badge column); First seen is `first_seen` as local `YYYY-MM-DD`; Role is ≤ 21 characters; every line is ≤ 100 columns with maximum-length names (FR-004, contracts/cli.md `check`).
  - Not found: `No application found for "Gogle".`, then `Did you mean: Google (#2)?` (and the form `Acme Inc. (#1, #5)`), then `Last sync: 2026-10-14 08:02 (complete)`, using the same wording as `render_last_sync`, including the incomplete forms.
  - No `Did you mean` line when there are no suggestions.
  - The quoted text is the user's raw input, printed literally (`[bold]x[/bold]` is not styled).
- [ ] T015 [P] [US1] Add failing CLI tests to `tests/unit/test_cli.py` (contracts/cli.md `check`; reuse `Harness` and copy `store_lookup.json` into `APPLYTRAIL_HOME`):
  - `check acme` → exit 0 with both Acme rows on stdout.
  - `check acme corp` (two arguments) is the same as `check "acme corp"`.
  - `check Initech` → exit 6 with the not-found lines on stdout.
  - `check "&"` → exit 2, stderr exactly `Enter a company name, for example: applytrail check acme`.
  - Empty or missing store → exit 6, stderr `No data yet. Run applytrail to sync.`
  - Unreadable store → exit 5 with the existing message.
  - The MCP client and extractor factories are never called.
  - Store file bytes are unchanged after every `check`.
  - `applytrail` and `applytrail --offline` behave exactly as before.

### Implementation

- [ ] T016 [US1] Add `InvalidInput(AppError)` with `exit_code = 2` that takes its message, in `src/applytrail/errors.py`. Add a test in `tests/unit/test_errors.py`.
- [ ] T017 [US1] Implement `normalize_query`, the frozen dataclasses `Suggestion(company: str, numbers: list[int], score: float)` and `LookupResult(query, matches, suggestions)` (property `found`), `find(store, text) -> LookupResult`, and the suggestion logic in `src/applytrail/lookup.py`:
  - Match the lookup words against both `norm_company(app.company)` and the company part of `app.key` (before `|`), each with the same trailing-`and` rule. Match on consecutive whole words, where the last word may be a prefix.
  - Suggestions use `difflib.SequenceMatcher` on the normalized text versus the whole name and every word run of the same length. Keep the best score per normalized company, apply cutoff `0.75`, keep at most 3, and use the display company of that company's newest application.
  - Make T012 and T013 pass.
- [ ] T018 [US1] Implement `render_found` and `render_not_found` in `src/applytrail/render.py`. `render_found` uses a new `build_check_table(store, rows)`: the columns from T014, with First seen at width 10 and Role at `max_width=21`, and the Company link as in `build_table`. Share the row-building code with `build_table` rather than duplicating it. Print all email-derived and user text with `markup=False, highlight=False` or as `Text`. When `last_sync_at` is null, the not-found answer prints `No sync has run yet.` Make T014 pass.
- [ ] T019 [US1] Add argparse subparsers to `src/applytrail/cli.py` with `add_subparsers(dest="command", required=False)` and a `check` subcommand (`names`, `nargs="+"`). `_check_command(settings, out, names)` loads the store, prints `NO_DATA_MESSAGE` and returns 6 when there are no applications and no sync, catches `InvalidInput` (it's an `AppError`, so the existing handler prints it and returns 2), and returns 0 when found or 6 when not found. Import no network module on this path. Make T015 pass.
- [ ] T020 [US1] Gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest` must all pass. Commit `feat(us1): check whether a company was already applied to`.

**Checkpoint**: The MVP is shippable: `check` works fully offline.

---

## Phase 4: User Story 2 - Open an application's email (Priority: P2)

**Goal**: `applytrail open TARGET... [--print]` prints the thread address of a row (by number or company name) and opens it in the browser where possible (FR-009 to FR-014, FR-016, FR-017). Links still use `u/0` until US3.

**Independent Test**: With `store_lookup.json` and a patched browser: `open 2` prints `Opening Google — Software Engineer (#2)` plus the `u/0` address, and the browser is called once with that address. `open 2 --print` doesn't call the browser. `open 99` exits 2 with the range message. `open acme` lists rows 1 and 5 and exits 2. `open initech` exits 6.

### Tests first (write, run, see them fail)

- [ ] T021 [P] [US2] Add failing tests to `tests/unit/test_links.py` (research R9):
  - `can_launch_browser(environ, platform)`: `SSH_CONNECTION` set → False. `linux` with neither `DISPLAY` nor `WAYLAND_DISPLAY` → False. `linux` with either → True. `darwin` and `win32` without SSH → True.
  - `open_in_browser(url) -> bool` calls `webbrowser.open(url, new=2)` (monkeypatched) and returns False when it returns False or raises `webbrowser.Error`.
- [ ] T022 [P] [US2] Add failing tests to `tests/unit/test_lookup.py` for `resolve(store, targets: list[str])`:
  - A single all-digit target `"2"` → a `NumberedApplication` for row 2.
  - `"0"`, `"99"` and `"8"` (with 7 rows) raise `InvalidInput("No row 99. Choose a number from 1 to 7 (see applytrail --offline).")`.
  - Non-digit targets are joined with spaces and passed to `find`, returning the `LookupResult`.
  - Empty or punctuation-only text raises `InvalidInput("Enter a row number or company name, for example: applytrail open 3")`.
- [ ] T023 [P] [US2] Add failing tests to `tests/unit/test_render.py` for `render_open(numbered, url, launching: bool, console)`:
  - Line 1 is `Opening Acme Inc. — Backend Engineer (#1)` when `launching`, or `Address for …` otherwise.
  - A null role prints `Unknown`.
  - Line 2 is exactly the address, with no inserted line break even at console width 40 (`soft_wrap=True`).
  - The company `[bold]Evil[/bold]` prints literally.
- [ ] T024 [P] [US2] Add failing CLI tests to `tests/unit/test_cli.py` (contracts/cli.md `open`; patch `links.open_in_browser` and `links.can_launch_browser`):
  - `open 2` → exit 0, two stdout lines, browser called once with `https://mail.google.com/mail/u/0/#all/<thread of row 2>`.
  - `open 2 --print` → `Address for`, browser not called, exit 0.
  - `can_launch_browser` False → `Address for`, browser not called, exit 0.
  - Browser returns False → stderr `Could not open a browser; use the address above.`, exit 0.
  - `open 99` → exit 2 with the range message.
  - `open google` → opens row 2.
  - `open acme` → the `check` table with rows 1 and 5 on stdout, stderr `Several applications match "acme". Run: applytrail open <number>`, exit 2, browser not called.
  - `open initech` → the not-found output on stdout, exit 6.
  - `open "&"` → exit 2.
  - No data → exit 6.
  - Store bytes unchanged, and no MCP client or extractor created.

### Implementation

- [ ] T025 [US2] Implement `can_launch_browser(environ=os.environ, platform=sys.platform) -> bool` and `open_in_browser(url) -> bool` (stdlib `webbrowser`, `new=2`, catches `webbrowser.Error`) in `src/applytrail/links.py`. Make T021 pass.
- [ ] T026 [US2] Implement `resolve(store, targets)` in `src/applytrail/lookup.py`. It returns `NumberedApplication | LookupResult` and raises `InvalidInput` with the exact messages from T022. Make T022 pass.
- [ ] T027 [US2] Implement `render_open(numbered, url, launching, console)` in `src/applytrail/render.py`: line 1 with `markup=False, highlight=False`, line 2 with `soft_wrap=True, highlight=False`. Make T023 pass.
- [ ] T028 [US2] Add the `open` subcommand (`targets`, `nargs="+"`; `--print`, `store_true`) and `_open_command` to `src/applytrail/cli.py`:
  - Show the no-data message (exit 6) when there are no applications and no sync.
  - Resolve the target. When several match, print `render.build_check_table(store, rows=matches)` and the stderr message, then exit 2. When none match, call `render.render_not_found` and exit 6.
  - When one matches: `url = links.thread_url(app.thread_id)`; `launching = not args.print and links.can_launch_browser()`; call `render_open`; if launching and `open_in_browser(url)` returns False, print the stderr note. Exit 0.
  - Make T024 pass.
- [ ] T029 [US2] Gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest` must all pass. Commit `feat(us2): open an application's Gmail thread from the terminal`.

**Checkpoint**: Every row can be opened by number or name, with or without a browser.

---

## Phase 5: User Story 3 - Open in the right Google account (Priority: P3)

**Goal**: Each sync detects the synced account through the new read-only MCP tool `get_account` and saves it as `sync.mailbox`. The table link and `open` address use `u/<mailbox>` (FR-015; research R7, R8).

**Independent Test**: A sync with a fake MCP whose `get_account` returns `me+jobs@example.com` saves that value. A second sync with the same account leaves the store byte-identical apart from `last_sync_at`. `open 1 --print` and the table hyperlink both use `https://mail.google.com/mail/u/me%2Bjobs@example.com/#all/<thread>`. With no mailbox saved, both use `u/0`.

### Tests first (write, run, see them fail)

- [ ] T030 [US3] Extend the test fakes in `tests/fakes.py` (test infrastructure, needed by T031–T036):
  - `FakeMcpClient.get_account()` returns `AccountInfo(email_address=self.account)`, where `account` is a new constructor argument defaulting to `"me@example.com"`. It records the call and can be configured to raise an `AppError`.
  - `FakeGmailService.users().getProfile(userId="me")` returns a `FakeGmailRequest` with `{"emailAddress": ...}` or a configured error.
- [ ] T031 [P] [US3] Add failing model tests to `tests/unit/test_models.py` and `tests/unit/test_store.py` (data-model.md):
  - `SyncState.mailbox` defaults to `None`.
  - Validation is "3–254 characters, exactly one `@`, no whitespace or control characters". Reject `"a"`, `"a@b@c"`, `"me @x.com"`, `"me\n@x.com"`, and a 255-character value. Accept `me+jobs@example.com`.
  - `AccountInfo.email_address` uses the same rule.
  - A store JSON without the `mailbox` key loads with `None`.
  - Saving twice with the same mailbox gives byte-identical files.
- [ ] T032 [P] [US3] Add failing tests to `tests/unit/test_links.py`: `thread_url("18c0aa01", "me+jobs@example.com")` equals `https://mail.google.com/mail/u/me%2Bjobs@example.com/#all/18c0aa01` (mailbox encoded with `quote(mailbox, safe="@")`), and `mailbox=None` still gives `u/0`.
- [ ] T033 [P] [US3] Add failing tests to `tests/unit/test_gmail_client.py`: `gmail_client.get_account(service)` calls `users().getProfile(userId="me")` and returns `AccountInfo`. HTTP 429 → `GmailRateLimited`, HTTP 500 → `GmailError(500)`, `OSError` → `NetworkUnavailable`, all through `_mapped_errors`.
- [ ] T034 [P] [US3] Update `tests/contract/test_mcp_tools.py` and add failing tests:
  - Both tool-set assertions (currently around lines 73 and 259) become `{"search_job_emails", "get_email", "get_account"}`.
  - `get_account` takes no arguments and returns `structured_content == {"email_address": "me@example.com"}`.
  - Missing auth → `is_error` with text starting `AUTH_REQUIRED:`.
  - The tool has a docstring description.
  - No listed tool name contains any of the `FORBIDDEN` words.
- [ ] T035 [P] [US3] Add failing tests to `tests/unit/test_mcp_client.py`: `GmailMcp.get_account()` (in-process server) returns `AccountInfo`, and the error prefixes map to the same typed errors as the other tools.
- [ ] T036 [P] [US3] Add failing integration tests to `tests/integration/test_sync_first_run.py` and `tests/integration/test_sync_incremental.py`:
  - A first sync saves `sync.mailbox == "me@example.com"`.
  - `get_account` is called exactly once per run, before `search_job_emails`.
  - A re-run with no new mail and the same account leaves the store unchanged apart from `last_sync_at` (reuse the existing checksum helper).
  - A run with a different account replaces the mailbox.
  - `get_account` raising `AuthRequired` stops the run as a search failure would, leaving the existing mailbox untouched.
- [ ] T037 [P] [US3] Add failing tests to `tests/unit/test_render.py` and `tests/unit/test_cli.py`:
  - With `store.sync.mailbox = "me+jobs@example.com"`, the table's Company `href` and `open 1 --print`'s address both use `u/me%2Bjobs@example.com`.
  - Without a mailbox, both use `u/0`.
  - The mailbox never appears in stderr output or in `debug.log`.

### Implementation

- [ ] T038 [US3] Add `mailbox: str | None = None` to `SyncState` and a new `AccountInfo(email_address: str)` model in `src/applytrail/models.py`. Both share one validator: "3–254 characters, exactly one `@`, no whitespace or control characters". `schema_version` stays `1`. Make T031 pass.
- [ ] T039 [US3] Add `get_account(service) -> AccountInfo` (inside `_mapped_errors`, `execute(num_retries=NUM_RETRIES)`) to `src/applytrail/gmail_client.py`. Update the module docstring to list `users().getProfile` alongside `messages().list` and `messages().get`. Make T033 pass.
- [ ] T040 [US3] Add the `get_account` tool to `src/applytrail/mcp_server.py`: `@server.tool`, no arguments, returns `AccountInfo`, wrapped in `_call`, with the docstring "Return the address of the Gmail account this server reads, so links can open the right mailbox." Never log the address. Make T034 pass.
- [ ] T041 [US3] Add `get_account() -> AccountInfo` to `GmailMcp` in `src/applytrail/mcp_client.py` using `_call("get_account", {})`. Make T035 pass.
- [ ] T042 [US3] Add `get_account()` to the `MailSource` protocol in `src/applytrail/sync.py`. In `run_sync`, inside the existing `try` and before `_candidates`, set `store.sync.mailbox = mcp.get_account().email_address`. Don't reset it with the badges. Make T036 pass.
- [ ] T043 [US3] Pass `store.sync.mailbox` to `links.thread_url` in `render.build_table` (`src/applytrail/render.py`) and in `_open_command` (`src/applytrail/cli.py`). Make T037 pass.
- [ ] T044 [US3] Gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest` must all pass. Commit `feat(us3): open threads in the synced Google account`.

**Checkpoint**: All three stories work, and links target the synced account.

---

## Phase 6: Polish & cross-cutting

- [ ] T045 [P] Add a performance test (SC-002) to `tests/unit/test_lookup.py`, modelled on `tests/unit/test_render_perf.py`: a generated 500-application store runs `numbered`, `find("acme")`, `find("zzzz")` (worst case, with suggestions) and `resolve(["250"])`, each under 1 s.
- [ ] T046 [P] Update `README.md`:
  - `applytrail check NAME...` and `applytrail open TARGET... [--print]` with examples.
  - Row numbers can change after a sync, and `open` always names what it opens.
  - Exit codes 0/2/6 for `check`/`open`.
  - Over SSH or with no display, only the address is printed.
  - Multi-account links use the synced account, which is detected at each sync.
  - The MCP tools list gains `get_account`.
  - The `#` table column.
- [ ] T047 [P] Update `AGENTS.md` rule 1 and the Project paragraph so the MCP read tools are listed as `search_job_emails`, `get_email`, `get_account`.
- [ ] T048 Run quickstart scenarios Q1–Q4 and Q7 from `specs/002-lookup-open-email/quickstart.md` and append a `## Results` section with date, command and observed outcome for each. Mark Q5 and Q6 (real Gmail, two browser accounts) as **pending user sign-off**: they need the user's mailbox and browser.
- [ ] T049 Gate: `uv run ruff check . && uv run ruff format --check . && uv run pytest` must all pass. Commit `docs: document check and open commands`.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001–T003)**: no dependencies.
- **Foundational (T004–T011)**: after Setup. Blocks every story.
- **US1 (T012–T020)**: after Foundational.
- **US2 (T021–T029)**: after US1. It reuses `find`, `render_not_found`, `InvalidInput`, and the subparser setup in `cli.py`.
- **US3 (T030–T044)**: after Foundational for the sync/MCP half (T030–T036, T038–T042). T037/T043 need US2's `_open_command`. Run it after US2 in practice, because all three stories edit `cli.py` and `render.py`.
- **Polish (T045–T049)**: after US3.

### Within each phase

- Test tasks first. Run them and confirm they fail for the expected reason (missing symbol or assertion), not because of a syntax error.
- Then the implementation, in the listed order. Then the gate, then the commit.
- Same-file tasks are never marked [P] with each other: `test_lookup.py` (T012 → T013), and `render.py`/`cli.py` are always sequential.

### Story independence

- US1 is shippable alone (the MVP).
- US2 works without US3, falling back to `u/0` links (spec US3 scenario 3).
- US3 makes no change to `check` behaviour.

## Parallel Examples

```text
# Foundational tests (different files):
T004 tests/unit/test_lookup.py   |  T005 tests/unit/test_links.py  |  T006 tests/unit/test_render.py

# US1 tests:
T012 tests/unit/test_lookup.py   |  T014 tests/unit/test_render.py |  T015 tests/unit/test_cli.py
# (T013 follows T012 in the same file)

# US2 tests:
T021 test_links.py | T022 test_lookup.py | T023 test_render.py | T024 test_cli.py

# US3 tests (after T030 fakes):
T031 test_models.py+test_store.py | T032 test_links.py | T033 test_gmail_client.py
T034 contract/test_mcp_tools.py   | T035 test_mcp_client.py | T036 integration/ | T037 test_render.py+test_cli.py

# US3 implementation: T039 (gmail_client) and T041 (mcp_client) touch different files, but
# both need T038 (models); T040 needs T039; T042 needs T041.
```

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1. Stop and validate with quickstart Q1 and Q4. `check` alone answers the main question.
2. **+US2**: every row can be opened (quickstart Q2, Q3, Q7).
3. **+US3**: links work with several signed-in accounts (quickstart Q5, Q6, needing user sign-off).
4. **Polish**: docs, the performance check, and quickstart results.

Commits, in order: `feat(table): …` (foundation), `feat(us1): …`, `feat(us2): …`, `feat(us3): …`,
`docs: …` (polish). Setup changes (fixture, fake helper) go in the foundation commit.

## Notes

- Quote error and output text exactly from `contracts/cli.md`. Tests assert those strings.
- Never print email-derived text or the user's query through Rich markup.
- `check` and `open` must not import `mcp_client`, `extractor`, or `sync`.
- Don't add dependencies. Use stdlib `difflib`, `webbrowser`, and `urllib.parse` only.
- Check off each task in this file as it completes (AGENTS.md workflow).
