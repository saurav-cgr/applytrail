# Feature Specification: Application Lookup and Email Opening

**Feature Branch**: `002-lookup-open-email`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "Let the user find out whether they already applied to a company, and make every application's Gmail email easy to open from the terminal."

## Clarifications

### Session 2026-10-15

- Q: Should row references be row numbers that can change after a sync, or short fixed IDs that stay the same for each application? → A: Row numbers (1, 2, 3…) in the current newest-first order; they may change after a sync. No fixed IDs.
- Q: How should "open" make sure Gmail shows the right account when the browser is signed in to several Google accounts? → A: Detect the synced account's address automatically during sync, save it locally, and use it in every thread address. No user setting.
- Q: When a lookup finds no match, should it suggest close spellings of saved company names? → A: Yes. The answer stays "not found", but up to 3 close saved company names are listed with their row numbers. Close spellings never count as matches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check whether I already applied to a company (Priority: P1)

A job seeker sees an opening at a company and wants to know, before applying, whether they have
applied there before. They type the company name (in whatever spelling comes to mind) and get a
direct answer: either "yes", with each matching application's role, current status, and when it
was first and last seen, or "no", with the date of the latest sync so they know how current that
answer is.

**Why this priority**: This is the question the user asks most often, and today they can answer it
only by scanning the whole table by eye. It works from data already saved, so it delivers value
on its own with no other change.

**Independent Test**: With a saved store holding applications for "Acme Corp" (two roles) and
"Globex", look up "acme" and confirm both Acme applications are listed; look up "Initech" and
confirm a clear "no application found" answer that names the latest sync date.

**Acceptance Scenarios**:

1. **Given** a saved application for "Acme Corp", **When** the user looks up "acme",
   "ACME", "Acme, Inc." or "acme corp", **Then** the Acme application is reported as found, with
   its role, status, first-seen date and last-activity date.
2. **Given** two saved applications at "Acme Corp" for different roles, **When** the user looks up
   "acme", **Then** both applications are listed, newest activity first.
3. **Given** no saved application whose company matches, **When** the user looks up "Initech",
   **Then** the answer says no application was found and states when the latest sync ran (or that
   no sync has run yet).
4. **Given** a saved application for "Globex International", **When** the user looks up "globex",
   **Then** it is reported as a match (partial names match), and the output makes clear which
   saved company name was matched.
5. **Given** a saved application whose status is Rejected or Withdrawn, **When** the user looks it
   up, **Then** it is still reported as found, with that status shown.
6. **Given** the user is offline or Gmail is unreachable, **When** they look up a company,
   **Then** the answer is produced from saved data without contacting Gmail or the extraction
   model.
7. **Given** a saved application for "Google", **When** the user looks up "Gogle", **Then** the
   answer is "not found", followed by a "Did you mean" list that includes Google with its row
   number.

---

### User Story 2 - Open an application's email from the terminal (Priority: P2)

From the table (or from a lookup result) the user wants to read the email behind an application,
for example to re-read a rejection or find the recruiter's name. Each row shows a short reference
the user can pass to an "open" action, which opens that application's latest email thread in
Gmail in their web browser, in the mailbox that was synced. The address is also printed as plain
text so it still works where the terminal cannot open a browser or show clickable links (for
example over SSH).

**Why this priority**: Clickable company names already exist in terminals that support links,
but many terminals do not, and the existing link can land in the wrong Google account. This story
makes every row reliably openable everywhere. It is less urgent than answering "did I apply?".

**Independent Test**: With a saved store of three applications, show the table, note the reference
of the second row, run the open action with it, and confirm the browser opens that application's
thread and the printed address points to the same thread.

**Acceptance Scenarios**:

1. **Given** the table is shown, **When** the user reads any row, **Then** the row carries a short
   reference that is visible as plain text (not only as a link or colour).
2. **Given** a row reference, **When** the user opens it, **Then** the output names the
   application being opened (company and role) and the latest email thread for that application
   opens in the default web browser.
3. **Given** a row reference, **When** the user opens it with the print-only option, or no browser
   can be launched, **Then** the full Gmail address of the thread is printed and nothing else
   happens; a browser failure is not reported as an error when the address was printed.
4. **Given** a lookup result from User Story 1, **When** it lists matching applications, **Then**
   each one shows the same reference the table uses, so the user can open it directly.
5. **Given** the user passes a company name instead of a reference, **When** exactly one
   application matches, **Then** it opens; **When** several match, **Then** they are listed with
   their references and nothing is opened.
6. **Given** a reference that does not exist (for example 42 when there are 10 rows), **When** the
   user opens it, **Then** one actionable message explains the valid range and the command exits
   non-zero.

---

### User Story 3 - Open in the right Google account (Priority: P3)

A user whose browser is signed in to several Google accounts (for example personal and work)
opens an application, either with the open action or by clicking a company name, and Gmail shows
the thread in the account that ApplyTrail synced, not "conversation not found" in whichever
account happens to be first.

**Why this priority**: It fixes a real failure, but only for users who are signed in to more than
one account. Without it, User Story 2 still works for everyone else, using the browser's first
account as today.

**Independent Test**: Run a sync against a fake mailbox that reports its account address, confirm
the address is saved, and confirm that both the table link and the open action's printed address
name that account. Then check by hand in a browser signed in to two accounts, with the synced one
not first.

**Acceptance Scenarios**:

1. **Given** the user is signed in to several Google accounts in their browser, **When** they open
   an application, **Then** Gmail shows the thread in the mailbox that ApplyTrail synced, not in
   whichever account happens to be first.
2. **Given** a sync completes, **When** the user inspects the saved data, **Then** the synced
   account's address is recorded, and the next sync with the same account leaves the saved data
   unchanged.
3. **Given** no account address has been saved yet, **When** the user opens an application,
   **Then** it opens in the browser's first account, as before, with no error.

---

### Edge Cases

- **No data yet**: lookup or open before any sync prints the existing "No data yet. Run
  applytrail to sync." message rather than "not found".
- **Empty or punctuation-only lookup text** (for example `""` or `"&"`): rejected with one
  actionable message; it must not match every application.
- **Very short lookup text** (one or two characters): still allowed, but because partial matching
  may return many rows, the results are listed like any other multi-match.
- **Legal suffixes and symbols**: "Acme Inc", "Acme, Inc.", "ACME Corporation" and "Acme & Co"
  normalize the same way the store already normalizes company keys, so they match each other.
- **Lookup text matching only a role** (for example "engineer"): not a match; lookup is by
  company name only.
- **References after a sync**: a new sync can reorder rows. The open action always resolves the
  reference against the current saved data and names the application it opens, so a stale number
  never silently opens an unexpected email without saying which one.
- **No synced mailbox saved yet** (store last synced before this feature existed): open still
  works, falling back to the browser's first signed-in account, and is not an error; the next sync
  saves the address.
- **Synced account changes** (user re-authorizes with a different Google account): the next sync
  replaces the saved address; addresses always use the latest one.
- **Email deleted from Gmail since the sync**: the thread opens to Gmail's own "not found" page;
  ApplyTrail does not check (it makes no network call for open).
- **Untrusted text**: company names, roles and subjects shown in lookup results are displayed as
  plain text and are never interpreted as markup, links or commands; the opened address is built
  only from Gmail identifiers, never from email text.

## Requirements *(mandatory)*

### Functional Requirements

**Lookup (User Story 1)**

- **FR-001**: Users MUST be able to look up a company by name from the terminal and get an
  explicit found / not-found answer.
- **FR-002**: Lookup MUST normalize the lookup text with the same company normalization used for
  stored applications (case, punctuation, "&", and legal suffixes such as Inc, Ltd, Corp, GmbH).
- **FR-003**: Lookup MUST match when the normalized lookup text equals a stored company's
  normalized name, or when its words appear in that name as consecutive whole words, the last of
  which may be the start of a word (so "globex" and "glob" match "Globex International",
  "international" matches it too, but "lob" does not).
- **FR-004**: For each match, lookup MUST show company, role (or "Unknown"), status as text, first
  seen date (approximately when the user applied, which matters for company re-apply windows),
  last activity date, and the row number used by the open action; matches are ordered newest
  activity first. The main table is unchanged: first seen appears only in lookup results.
- **FR-005**: A not-found answer MUST state when the latest sync ran and whether it completed, or
  that no sync has run.
- **FR-005a**: A not-found answer MUST list up to 3 saved company names that are close in spelling
  to the lookup text (most similar first, each with its row number), or nothing when none is close
  enough. Suggestions are deterministic for the same saved data and lookup text, and never turn a
  not-found answer into a found one (the exit status stays "not found").
- **FR-006**: Lookup MUST use only saved data: no Gmail access, no extraction model, no change to
  the saved data.
- **FR-007**: Lookup's exit status MUST distinguish "found" from "not found", and both MUST differ
  from the exit status used for errors, so scripts can rely on it.
- **FR-008**: Lookup MUST reject empty or punctuation-only text with one actionable message and a
  non-zero exit status.

**Opening emails (User Story 2; FR-015 is User Story 3)**

- **FR-009**: Every table row MUST show its row number (1, 2, 3…) as plain text; this number is
  the row reference. The table MUST stay readable at 100 columns.
- **FR-010**: Row numbers MUST be the 1-based position in the table's existing newest-first order
  of the current saved data, so the same saved data always yields the same numbers in the table,
  in lookup results, and in the open action. Numbers may change after a sync; no fixed per-
  application ID exists.
- **FR-011**: Users MUST be able to open an application by reference; this opens the application's
  latest email thread in Gmail in the default web browser.
- **FR-012**: Users MUST also be able to open by company name; exactly one match opens it,
  several matches are listed with their references and nothing opens, and no match gives the
  not-found answer.
- **FR-013**: Before opening, the output MUST name the application (company and role) and print
  the full thread address as plain text.
- **FR-014**: A print-only option MUST print the address without launching a browser. When a
  browser cannot be launched, the printed address is the result and the command still succeeds.
- **FR-015**: The thread address MUST target the Gmail mailbox that was synced, so it opens
  correctly when the browser is signed in to several Google accounts. Each sync MUST detect the
  synced account's address automatically (read-only, no user setting) and save it locally; the
  table link and the open action both use it. If no address has been saved yet, the address falls
  back to the browser's first signed-in account.
- **FR-016**: Opening MUST make no network call and MUST NOT change the saved data. The address
  MUST be built only from Gmail identifiers and the synced mailbox, never from email text.
- **FR-017**: An unknown reference MUST print one actionable message naming the valid range and
  exit non-zero, without a stack trace.

**Shared**

- **FR-018**: Lookup and open MUST show the existing "No data yet" message when nothing has been
  synced.
- **FR-019**: Company names, roles and other email-derived text MUST be displayed as plain text,
  never interpreted as terminal markup.
- **FR-020**: Gmail access MUST remain read-only; this feature adds no write capability and no new
  permission.
- **FR-021**: The README MUST document the lookup and open actions, the print-only option, and how
  references behave after a sync.

### Key Entities

- **Application** (existing): company, role, status, first seen, last activity, latest thread
  identifier. Unchanged in meaning; lookup and open read it.
- **Row reference**: short plain-text label for an application, derived from its position in the
  newest-first order of the current saved data. Not stored; recomputed whenever shown or resolved.
- **Synced mailbox**: the address of the Gmail account whose mail was synced, detected during each
  sync and saved locally (owner-only, like the rest of the store) so thread addresses open in the
  right account. One per store; contains no email content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can answer "did I already apply to X?" with one command in under 5 seconds,
  without scrolling the table.
- **SC-002**: For a store of 500 applications, lookup and open each return in under 1 second on the
  reference laptop, with no network access.
- **SC-003**: On a labelled set of at least 20 spelling variants of stored company names (case,
  punctuation, legal suffixes, partial names), lookup finds the intended application in 100% of
  cases and returns no false matches for 10 unrelated names.
- **SC-003a**: On a labelled set of at least 10 one- or two-letter typos of stored company names,
  the intended company appears among the not-found suggestions in at least 90% of cases.
- **SC-004**: 100% of table rows can be opened by reference, in terminals with and without
  clickable-link support, including over a remote session where only the printed address is used.
- **SC-005**: When the browser is signed in to two or more Google accounts, opening an application
  shows the thread in the synced mailbox in 100% of tested cases.
- **SC-006**: The table with references fits in 100 columns with no row wrapping.

## Assumptions

- Lookup is by company only. Searching by role, status or date is out of scope.
- "Already applied" means a saved application exists in any status, including Rejected and
  Withdrawn. Emails that were ignored or skipped during sync do not count.
- Answers reflect the latest sync. Lookup and open do not sync first; the user runs the default
  command to refresh. The not-found answer shows the sync date so staleness is visible.
- Matching is deterministic (normalized word match, FR-003), not fuzzy or typo-tolerant. A
  misspelling such as "Gogle" is not found, but the not-found answer suggests close spellings
  (FR-005a); this keeps the found / not-found answer predictable while catching typos.
- References are row numbers in the current newest-first order and may change after a sync; this
  is acceptable because the open action always names what it opens.
- "The email" for an application is its latest thread, which is what the table already links to.
  Opening older emails of the same application is out of scope.
- Opening uses the system's default browser. When none is available, printing the address is the
  supported fallback.
- Recording which mailbox was synced is allowed by the read-only permission already granted; no new
  permission is needed.
- The existing clickable company link in the table is kept and points to the same address as the
  open action.
