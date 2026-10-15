# Research: Application Lookup and Email Opening

**Feature**: `002-lookup-open-email` | **Date**: 2026-10-15

Constraint from the user: existing stack only, no new dependency. Every decision below uses the
standard library or code already in `src/applytrail/`.

## R1. Command shape

**Decision**: Two optional argparse subcommands next to the existing default:
`applytrail check NAME...` and `applytrail open TARGET... [--print]`. `applytrail` and
`applytrail --offline` keep their current behaviour. Multi-word names are passed as several
arguments and joined with single spaces, so `applytrail check acme corp` works without quotes.

**Rationale**: Subcommands read as the question being asked ("check acme", "open 3"). argparse
supports `add_subparsers(required=False)`, so the default command needs no change.

**Alternatives considered**: Flags `--check NAME` / `--open REF` (they mix with `--offline` in
confusing ways, for example `--offline --open 3`). Separate entry points `applytrail-check` (more
scripts to install, and harder to find in `--help`).

## R2. Exit codes

**Decision**:

| Code | `check` | `open` |
|---|---|---|
| 0 | At least one application found | Address printed (browser opened or not) |
| 2 | Empty or punctuation-only name | Empty name, unknown row number, or several matches |
| 5 | Store unreadable (existing) | Store unreadable (existing) |
| 6 | Not found, or no data yet | No match, or no data yet |

**Rationale**: FR-007 needs found and not-found to differ from each other and from errors. Codes 1,
3, 4 and 130 are already taken by error conditions (contracts/cli.md), so not-found can't reuse 1
the way `grep` does. 6 is the next free code. 2 is already "fix your setup or input" (argparse also
exits 2 on usage errors). "No data yet" is reported as not found (6) because ApplyTrail can't
confirm an application, and a script must never read it as "found".

**Alternatives considered**: Not found exits 1 (clashes with unexpected errors). Not found exits 0
with only the text differing (scripts can't tell found and not found apart, which fails FR-007).

## R3. Lookup normalization and matching

**Decision**: Normalize the lookup text with the existing `normalize.norm_company`, then drop a
trailing `and` word (left behind when "& Co" loses its legal suffix, as in "Acme & Co" →
`acme and`). Apply the same to each application's display company and to the company part of its
key. An application matches when the lookup words `L` appear in either word list `C` as a
consecutive run, every word equal except the last, which may be a prefix:
`C[i:i+n-1] == L[:-1]` and `C[i+n-1].startswith(L[-1])`, where `n = len(L)`. An empty `L` (input
that was empty or only punctuation) is rejected (FR-008).

**Rationale**: Reusing `norm_company` makes lookup agree with how sync already decides that two
spellings are the same company (FR-002). Word-boundary prefix matching lets "glob" find "Globex
International" but stops "lob" from matching it (FR-003). Checking both the display name and the
key covers an application whose display spelling changed after a later email. The trailing-`and`
rule is lookup-only. Changing `norm_company` would change the keys of stores that already exist.

**Alternatives considered**: Plain substring match (false positives such as "ac" matching
"Tracer"). Typo-tolerant matching (rejected in clarification Q3: a typo gives not-found plus
suggestions, never a match).

## R4. "Did you mean" suggestions

**Decision**: Use stdlib `difflib.SequenceMatcher`. For each saved company (one entry per
normalized company), score it as the highest ratio between the normalized lookup text and (a) the
whole normalized company name or (b) every run of the same number of words in it. Keep scores
≥ 0.75, sort by score descending and then by name, and take the first 3. Each suggestion shows the
display company and the row numbers of its applications.

**Rationale**: Deterministic and stdlib only (FR-005a). Comparing word runs lets "globx" find
"Globex International", which a whole-string ratio would score too low. A 0.75 cutoff catches one-
and two-letter typos on names of five or more letters ("gogle" vs "google" is 0.91, "amazn" vs
"amazon" is 0.91) and leaves unrelated names out. SC-003a is checked by a labelled test list in
`tests/unit/test_lookup.py`, and the cutoff is tuned against that list, not changed ad hoc.

**Alternatives considered**: `difflib.get_close_matches` on whole names only (misses partial
names). Levenshtein distance (needs a dependency or hand-written code that isn't more accurate).

## R5. Row numbers

**Decision**: Row number = 1-based position in `sorted(applications, key=render.sort_key)`. One
function, `lookup.numbered(store)`, produces the list. The table, the `check` results and `open`
all use it. Nothing is stored.

**Rationale**: Clarification Q1. One source of ordering means the three views can't disagree
(FR-010).

## R6. Table width with the new column

**Decision**: Add a `#` column first, right-aligned, as wide as the largest row number (3 for up
to 999 rows). Narrow Company from 28 to 25 and Role from 30 to 27. With `box.SQUARE` the total is
3+4+25+27+12+10 = 81 for content, plus 7 borders and 12 padding = 100 (FR-009, SC-006).

**Rationale**: Company and Role already ellipsize, so they're the right columns to give up width.
Status and date must stay whole.

**Alternatives considered**: Putting the number inside the badge column (`3 NEW`), which mixes two
meanings in one cell. Dropping the Last seen column (it carries information the user relies on).

## R7. Detecting the synced mailbox

**Decision**: Add one read-only MCP tool, `get_account`. It calls Gmail
`users().getProfile(userId="me")` and returns `{"email_address": "..."}`. `run_sync` calls it once
per run, before searching, and stores the result in `store.sync.mailbox`. It fails with the same
`AUTH_REQUIRED:` / `NETWORK:` / `RATE_LIMITED:` / `GMAIL_ERROR:` errors as the other tools.

**Rationale**: `getProfile` is allowed by the `gmail.readonly` scope already granted, so no new
scope is needed (Principle I: only write tools or new scopes need a MAJOR amendment). A separate,
task-shaped tool keeps the existing tool outputs unchanged, and MCP clients such as Claude Desktop
can use it too (Principle VI). One call per sync is negligible against the performance target.

**Alternatives considered**: Adding `email_address` to the `search_job_emails` output (couples
two concerns and changes an existing contract). Reading the address from the OAuth token (the
token holds no address unless the `openid email` scope is added, which would be a new scope). A
user setting (rejected in clarification Q2).

## R8. Gmail thread address

**Decision**: `https://mail.google.com/mail/u/{mailbox}/#all/{thread_id}`, where `mailbox` is
percent-encoded with `urllib.parse.quote(mailbox, safe="@")` and `thread_id` with
`quote(thread_id, safe="")`. When `mailbox` is null, use `u/0` (the current behaviour). One
function, `links.thread_url(thread_id, mailbox)`, builds the address for both the table hyperlink
and `open`.

**Rationale**: Gmail accepts an account address in place of the account index in `/mail/u/…/`,
which selects the right account however many are signed in (FR-015). Both parts come from Gmail
API identifiers, never from email text, and both are percent-encoded so a hand-edited store can't
inject anything into the address (FR-016).

**Verification**: `quickstart.md` scenario Q6 checks this by hand in a browser signed in to two
accounts. If Gmail ever stops accepting the address form, the fallback is
`https://mail.google.com/mail/?authuser={mailbox}#all/{thread_id}`, which is a one-line change in
`links.py`.

## R9. Opening the browser

**Decision**: Always print the address to stdout first. Then, unless `--print` was given or no
graphical session is detected, call stdlib `webbrowser.open(url, new=2)`. A session counts as "no
graphical session" when `SSH_CONNECTION` is set, or when the platform is Linux and neither
`DISPLAY` nor `WAYLAND_DISPLAY` is set. If `webbrowser.open` returns `False` or raises
`webbrowser.Error`, print one stderr note (`Could not open a browser; use the address above.`) and
still exit 0 (FR-014).

**Rationale**: On a headless Linux box, `webbrowser` falls back to console browsers (lynx, w3m),
which would take over the terminal and can't sign in to Gmail anyway. Skipping the launch there
makes the printed address the result, which is the supported fallback. Printing first means the
address is shown even if launching the browser hangs or fails.

**Alternatives considered**: Calling `open`/`xdg-open` through `subprocess` (more code for each
platform, and the same detection problem). Never launching, print only (worse on a desktop, where
one command should open the email).

## R10. Output safety

**Decision**: All text derived from email (company, role) and the user's lookup text is printed as
`rich.text.Text` or with `markup=False, highlight=False`. The `open` address is printed with
`soft_wrap=True` so Rich doesn't insert line breaks into it.

**Rationale**: FR-019. A company name such as `[link=…]X[/link]` must print literally. A broken
URL can't be copied.
