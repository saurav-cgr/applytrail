# Quickstart: Application Lookup and Email Opening

**Feature**: `002-lookup-open-email` | Validation guide. Behaviour details are in
[contracts/cli.md](contracts/cli.md). Design decisions are in [research.md](research.md).

## Prerequisites

- `uv sync` done. For Q5–Q7 you also need a working `applytrail-auth` token and Ollama (existing
  README setup).
- Q1–Q4 need no Gmail, no Ollama, and no network.

## Automated checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Expected: everything passes. New tests: `tests/unit/test_lookup.py` (matching, numbering,
suggestions, including the SC-003 and SC-003a labelled lists), `tests/unit/test_links.py`
(address building, browser decision), and additions to `test_render.py`, `test_cli.py`,
`test_models.py`, `test_gmail_client.py`, `tests/contract/test_mcp_tools.py`, and
`tests/integration/test_sync_*.py` (mailbox saved).

## Q1. Lookup found / not found (offline, scratch store)

```bash
export APPLYTRAIL_HOME="$(mktemp -d)"
# Copy a store holding Acme Inc. (2 roles), Globex International, Google (anonymized fixture):
cp tests/fixtures/store_lookup.json "$APPLYTRAIL_HOME/applications.json"
uv run applytrail check acme;         echo "exit $?"   # 2 rows, exit 0
uv run applytrail check "Acme, Inc."; echo "exit $?"   # same 2 rows, exit 0
uv run applytrail check glob;         echo "exit $?"   # Globex International, exit 0
uv run applytrail check lob;          echo "exit $?"   # not found, exit 6
uv run applytrail check Gogle;        echo "exit $?"   # not found + "Did you mean: Google (#n)?", exit 6
uv run applytrail check "&";          echo "exit $?"   # one-line message, exit 2
```

## Q2. Row numbers agree everywhere

```bash
uv run applytrail --offline        # note the # of Globex
uv run applytrail check globex     # same number
uv run applytrail open globex --print   # "Address for Globex International — … (#same)"
```

## Q3. Open by number, print-only, bad input

```bash
uv run applytrail open 2 --print; echo "exit $?"    # name line + address, exit 0, no browser
uv run applytrail open 99;        echo "exit $?"    # "No row 99. Choose a number from 1 to N …", exit 2
uv run applytrail open acme;      echo "exit $?"    # table of 2 Acme rows + "Several applications match", exit 2
```

## Q4. No data, width, untrusted text

```bash
APPLYTRAIL_HOME="$(mktemp -d)" uv run applytrail check acme; echo "exit $?"  # "No data yet…", exit 6
COLUMNS=100 uv run applytrail --offline    # no row wraps; # column visible
```

Store fixture includes a company named `[bold]Evil[/bold]`: it prints literally in every view.

## Q5. Mailbox is detected by sync (real Gmail)

```bash
unset APPLYTRAIL_HOME
uv run applytrail                      # normal sync
python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.applytrail/applications.json')))['sync']['mailbox'])"
```

Expected: the address you authorized with `applytrail-auth`.

## Q6. Right account with several accounts signed in (manual, SC-005)

1. Sign the default browser in to two Google accounts, with the synced one **not** first.
2. `uv run applytrail open 1`.
3. Expected: Gmail opens the thread in the synced account. Repeat by clicking the Company link
   in a terminal that supports links (iTerm2, recent macOS Terminal, VS Code). Record the result in
   the PR. If it fails, apply the `authuser` fallback (research R8) and repeat.

## Q7. Headless session

```bash
ssh localhost 'cd ~/projects/applytrail && uv run applytrail open 1'
```

Expected: `Address for …` plus the address, no browser and no console browser starts, exit 0.

## Results

Run 2026-10-15 on branch `002-lookup-open-email` (after `feat(us3)`), with a scratch
`APPLYTRAIL_HOME` holding a copy of `tests/fixtures/store_lookup.json`. `BROWSER=/usr/bin/true`
was set for every run, so no real browser could start. The store's SHA-256 was the same before
and after all of Q1–Q4 and Q7.

| Scenario | Command | Observed |
|---|---|---|
| Q1 | `applytrail check acme` | `Found 2 applications matching "acme":`, rows #1 and #5, columns `#, First seen, Company, Role, Status, Last seen`; exit 0 |
| Q1 | `applytrail check "Acme, Inc."` | Same 2 rows; exit 0 |
| Q1 | `applytrail check glob` | `Found 1 application matching "glob":`, Globex International (#3); exit 0 |
| Q1 | `applytrail check lob` | `No application found for "lob".`, `Last sync: 2026-10-14 13:32 (complete)`; exit 6 |
| Q1 | `applytrail check Gogle` | Not found, then `Did you mean: Google (#2)?` and the Last sync line; exit 6 |
| Q1 | `applytrail check "&"` | `Enter a company name, for example: applytrail check acme`; exit 2 |
| Q2 | `applytrail --offline`, `check globex`, `open globex --print` | Globex is #3 in all three; `Address for Globex International — Unknown (#3)` and `https://mail.google.com/mail/u/0/#all/18c0aa03`; exit 0 |
| Q3 | `applytrail open 2 --print` | `Address for Google — Software Engineer (#2)` and the `u/0` address; exit 0; no browser |
| Q3 | `applytrail open 99` | `No row 99. Choose a number from 1 to 7 (see applytrail --offline).`; exit 2 |
| Q3 | `applytrail open acme` | `check` table with rows #1 and #5, then `Several applications match "acme". Run: applytrail open <number>`; exit 2 |
| Q4 | `check acme` with an empty `APPLYTRAIL_HOME` | `No data yet. Run applytrail to sync.`; exit 6 |
| Q4 | `COLUMNS=100 applytrail --offline` | 7 rows, `#` column visible, widest line 83 cells, no wrapped rows; `[bold]Evil[/bold]` printed literally (also literal in `check` and `open`, covered by tests) |
| Q7 | `SSH_CONNECTION="127.0.0.1 1 127.0.0.1 22" applytrail open 1` | `Address for Acme Inc. — Backend Engineer (#1)` and the address; no browser; exit 0. Simulated with the variable that `ssh` sets, not a real `ssh localhost` session |
| Q5 | Real Gmail sync, read `sync.mailbox` | **Pending user sign-off**: needs the user's mailbox |
| Q6 | `applytrail open 1` with two Google accounts signed in (SC-005) | **Pending user sign-off**: needs the user's browser and accounts |
