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
