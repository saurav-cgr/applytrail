# Contract: Command-Line Interface

## `applytrail`

```text
applytrail [--offline] [--version] [--help]
```

| Invocation | Behaviour |
|---|---|
| `applytrail` | Sync new mail, save, print table, print summary line |
| `applytrail --offline` | Print table from the store; no network, no MCP server started |

### Standard output

1. Table (see [Table layout](#table-layout)), or a one-line message when there are no
   applications: `No job applications found yet.`
2. Summary line (default command only):
   `Read 12 emails · 2 new · 1 updated · 8 ignored · 1 skipped`
   With `--offline`: `Last sync: 2026-10-14 08:02 (complete)` or `Last sync: 2026-10-14 08:02
   (incomplete — 230 emails pending; run applytrail to continue)`.

Progress on stderr during sync:
- Spinner text: `Loading qwen3:4b…` on the first call, then `Extracting 7/20`.
- If there are more than 50 candidates, print one line before extracting: `412 emails to process
  (~20 min with local model). Ctrl-C is safe; re-running continues where it stopped.` The time
  estimate uses 3 s per email.

Progress during sync goes to stderr (Rich status spinner) so stdout stays clean.

### Table layout

| Column | Width | Content |
|---|---|---|
| (badge) | 4 | `NEW`, `UPD`, or blank |
| Company | ≤ 28 | Ellipsized; hyperlink to Gmail thread where supported |
| Role | ≤ 30 | Ellipsized; `Unknown` when null |
| Status | 12 | Display label from the Status enum |
| Last activity | 10 | `YYYY-MM-DD` in local time |

Total width ≤ 100 columns including borders. Status and badges are text; colour only reinforces.

### Exit codes and messages

| Code | Condition | Message (stderr, single line) |
|---|---|---|
| 0 | Success (including "nothing new") | — |
| 0 | `--offline` with an empty or missing store | `No data yet. Run applytrail to sync.` |
| 2 | Not signed in / token invalid | `Gmail access not set up or expired. Run: applytrail-auth` |
| 2 | Ollama not reachable (preflight) | `Ollama is not running at <host>. Start the Ollama app or run: ollama serve` |
| 2 | Model not pulled | `Model <model> is not installed. Run: ollama pull <model>` |
| 3 | Network unavailable | `Cannot reach Gmail. Use applytrail --offline to view saved data.` |
| 4 | Ollama fails mid-sync (after 1 retry) | `Ollama stopped responding. N emails pending; progress saved. Run applytrail again.` |
| 4 | Gmail API rate limited (`RATE_LIMITED:` after server retry) | `Gmail rate limit reached. N emails pending; progress saved. Try again in a few minutes.` |
| 4 | Ollama out of memory | `Not enough memory to run <model>. Close other apps or set APPLYTRAIL_MODEL to a smaller model (e.g. llama3.2:3b).` |
| 5 | Store file unreadable | `Cannot read <path>. Move it aside and run applytrail to rebuild.` |
| 130 | Ctrl-C | `Interrupted. Progress saved.` |

For codes 3, 4 and 130, partial progress is saved before exit. For code 4, the table of saved
data **is** printed to stdout (badges show this run's partial changes) before the stderr message.
For network failure and Ctrl-C the table is not printed. Code 2 setup errors are detected by the
preflight before Gmail is contacted, so nothing is saved or changed.
No stack trace for any listed condition; unexpected errors print one line plus the path of a
debug log only when `APPLYTRAIL_DEBUG=1`.

## `applytrail-auth`

```text
applytrail-auth
```

Reads `$APPLYTRAIL_HOME/credentials.json` (Google OAuth Desktop client). Opens the browser consent
screen for scope `gmail.readonly` only. Writes `$APPLYTRAIL_HOME/token.json` (mode 0600).

| Code | Condition | Message |
|---|---|---|
| 0 | Token saved | `Gmail read-only access granted. Run applytrail.` |
| 2 | `credentials.json` missing | `Missing <path>. See README: Set up Google OAuth.` |
| 1 | User cancelled / flow failed | `Sign-in did not complete: <short reason>` |

## `applytrail-mcp`

Starts the MCP server on stdio. Intended to be launched by `applytrail` or an MCP client (MCP
Inspector, Claude Desktop). See [mcp-tools.md](mcp-tools.md).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `APPLYTRAIL_HOME` | `~/.applytrail` | Data folder: store, token, credentials |
| `APPLYTRAIL_MODEL` | `qwen3:4b` | Ollama model tag used for extraction |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server (Ollama's own variable). A non-loopback host prints a privacy warning |
| `APPLYTRAIL_DEBUG` | unset | `1` writes tracebacks to `$APPLYTRAIL_HOME/debug.log` |

A `.env` file in the current directory is loaded if present.
