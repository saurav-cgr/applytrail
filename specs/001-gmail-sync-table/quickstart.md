# Quickstart: Validate Gmail Sync and Application Table

Run guide proving the feature works end to end. Interfaces: [contracts/cli.md](contracts/cli.md),
[contracts/mcp-tools.md](contracts/mcp-tools.md). Data: [data-model.md](data-model.md).

## Prerequisites

- Python 3.11+ and `uv`.
- A Google Cloud project with the Gmail API enabled and an OAuth client of type **Desktop app**.
  Download its JSON to `~/.applytrail/credentials.json`.
- Ollama running locally (`ollama --version`; `curl -s localhost:11434/api/version`), with the
  extraction model pulled: `ollama pull qwen3:4b` (about 2.5 GB). About 3 GB of free RAM during
  sync. Email text is processed only on this machine.

## Setup

```bash
uv sync                 # install project + dev dependencies
uv run applytrail-auth  # browser consent, gmail.readonly only
```

Expected: `Gmail read-only access granted. Run applytrail.` and `~/.applytrail/token.json` with
mode `-rw-------`.

## Automated checks (no network)

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Expected: all pass; no test touches Gmail or a live model.

## Scenario 1 — First run (US1)

```bash
uv run applytrail
```

Expected:
- Table of applications, newest activity first, every row badged `NEW`.
- Summary line, e.g. `Read 143 emails · 37 new · 0 updated · 101 ignored · 5 skipped`.
- `~/.applytrail/applications.json` exists, mode `-rw-------`, contains no email bodies
  (`grep -c body_text ~/.applytrail/applications.json` prints `0`).
- stderr shows `Loading qwen3:4b…`, then `Extracting k/N`. With more than 50 candidates, an
  estimate line comes first. A 6-month first run takes about 10–25 min.
- Ctrl-C partway, then re-run: processed emails are not re-extracted (newest ones were done
  first).

## Scenario 2 — Idempotent re-run (US2, SC-004)

```bash
uv run applytrail
```

Run immediately after Scenario 1. Expected: `Read 0 emails · 0 new · 0 updated …`, no badges,
and `jq '.applications' ~/.applytrail/applications.json | shasum` unchanged from before.

## Scenario 3 — Badges (US2)

Send yourself a test email from another account with subject "Thank you for applying to Testco –
Data Analyst" and body "We have received your application for Data Analyst." Then:

```bash
uv run applytrail
```

Expected: one row `NEW  Testco  Data Analyst  Applied  <today>` at the top.

Send a second email: "Testco – Data Analyst: we'd like to schedule an interview." Re-run.
Expected: the same row shows `UPD` and status `Interview`; no other row is badged.

## Scenario 3b — Local model speed and memory (R3, SC-001)

```bash
/usr/bin/time -l uv run applytrail     # with ~20 new candidate emails since last sync
ollama ps                              # during or just after the run
```

Expected:
- Wall time is under 60 s for about 20 emails. If it is over, record the time and apply the R3
  mitigations (body cap 3,000 characters, then a shorter evidence quote).
- `ollama ps` shows `qwen3:4b` at about 3 GB, and it is gone after 5 minutes idle.
- macOS Activity Monitor shows no memory-pressure red during the run.

## Scenario 4 — Offline view (US3)

```bash
uv run applytrail --offline
```

With Wi-Fi off. Expected: same table and badges as the last sync, plus
`Last sync: … (complete)`. Exit code 0.

## Scenario 5 — Expected failures

| Step | Expected |
|---|---|
| `mv ~/.applytrail/token.json /tmp/ && uv run applytrail` | `… Run: applytrail-auth`, exit 2 |
| Quit the Ollama app, `uv run applytrail` | `Ollama is not running at http://127.0.0.1:11434 …`, exit 2, no Gmail call |
| `APPLYTRAIL_MODEL=nope:1b uv run applytrail` | `Model nope:1b is not installed. Run: ollama pull nope:1b`, exit 2 |
| Quit Ollama mid-sync | Retries once, then saved table prints and `Ollama stopped responding. N emails pending …`, exit 4 |
| Wi-Fi off, `uv run applytrail` | `… Use applytrail --offline …`, exit 3 |
| `echo '{' > ~/.applytrail/applications.json && uv run applytrail` (back up first) | `Cannot read …`, exit 5, file unchanged |
| Ctrl-C during a long sync, then re-run | `Interrupted. Progress saved.`, exit 130; re-run does not re-extract finished emails |

No stack trace in any case.

## Scenario 6 — MCP server stand-alone (Principle VI)

```bash
npx @modelcontextprotocol/inspector uv run applytrail-mcp
```

Expected: exactly two tools, `search_job_emails` and `get_email`; both callable; no write tools.

Without Node, use the FastMCP CLI that ships with the `fastmcp` dependency:

```bash
uv run fastmcp list --command "uv run applytrail-mcp" --input-schema --output-schema
```

Expected: the same two tools. Input schemas match [contracts/mcp-tools.md](contracts/mcp-tools.md)
(`after` required, `max_results` 1–500, `max_chars` 500–20000). Output schemas list the
`SearchPage` and `EmailMeta` fields.

## Scenario 7 — FastMCP migration parity

Run after replacing `MCPServer` with `FastMCP` (research R1).

```bash
uv run pytest tests/contract tests/unit/test_mcp_client.py tests/integration -q
uv run ruff check . && uv run ruff format --check .
uv run python -c "import importlib.metadata as m; print(m.version('fastmcp'), m.version('mcp'))"
APPLYTRAIL_HOME=$(mktemp -d) uv run fastmcp call --command "uv run applytrail-mcp" \
  --target search_job_emails --input-json '{"after": "2026-04-15T00:00:00Z"}'
```

Expected:

- All tests pass with no change to the asserted wire contract: tool names, schemas,
  `structured_content`, and error texts.
- `fastmcp` 4.x and `mcp` 2.3.x are installed.
- The last command (empty home, so no token) prints
  `Error: AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth.` and exits 1.
  The server's log lines (stderr) are allowed; a FastMCP banner is not.
- `applytrail` (full sync) and `applytrail --offline` behave exactly as in Scenarios 1–4.

## Golden-set evaluation (manual, when prompt/schema/model changes)

```bash
uv run python scripts/eval_extractor.py
```

Uses the local model from `APPLYTRAIL_MODEL`. Run it **before** building on the extractor, to
confirm `qwen3:4b` is good enough. Expected: prints company and status accuracy over
`tests/golden/`, plus mean seconds per email; target ≥ 90% (SC-003) and
zero rows from non-job emails. Record the result in the PR.
