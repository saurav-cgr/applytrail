# ApplyTrail

ApplyTrail is a terminal tool that keeps track of your job applications. It reads
job-application emails from Gmail (read-only), uses a local Ollama model to pull out the company,
role and status of each one, and shows the results as a table, newest first. A simplified example:

```text
  #       Company                      Role                           Status       Last seen
  1  NEW  Northwind Labs               Backend Engineer               Interview    2026-10-13
  2  UPD  Brightwave                   Data Engineer                  Rejected     2026-10-12
  3       Halcyon Systems              Platform Engineer              Applied      2026-10-02
Read 12 emails · 2 new · 1 updated · 8 ignored · 1 skipped
```

- `NEW` marks an application found in this sync; `UPD` marks one whose status, role or date
  changed. Badges and statuses are always text; colour only reinforces them.
- Each run fetches only mail that arrived since the last sync. A run with no new mail changes
  nothing.
- An older email never overwrites a newer status.
- `#` is the row number, used by `applytrail open`. The Company name links to the Gmail thread in
  terminals that support links.

## Install

Requires Python 3.11 or newer.

```bash
uv tool install .
# or
pipx install .
```

This installs three commands: `applytrail`, `applytrail-auth` and `applytrail-mcp`.

## Set up Google OAuth

ApplyTrail asks Google for the `gmail.readonly` scope only. It cannot send, delete, label,
archive or change any email.

1. Create a project in the [Google Cloud console](https://console.cloud.google.com/).
2. Enable the **Gmail API** for that project.
3. Configure the OAuth consent screen and add your own Google account as a test user.
4. Create an OAuth client ID of type **Desktop app** and download its JSON file.
5. Save the file as `~/.applytrail/credentials.json`.
6. Run:

   ```bash
   applytrail-auth
   ```

   A browser window opens for consent. When it finishes, you see
   `Gmail read-only access granted. Run applytrail.` and the token is saved to
   `~/.applytrail/token.json` with mode `0600`.

Run `applytrail-auth` again whenever ApplyTrail reports that Gmail access is not set up or has
expired.

## Set up Ollama

1. Install Ollama from [ollama.com](https://ollama.com) and start it (the Ollama app, or
   `ollama serve`).
2. Pull the extraction model (about 2.5 GB):

   ```bash
   ollama pull qwen3:4b
   ```

The model needs about 3 GB of RAM while a sync runs. ApplyTrail asks Ollama to unload it 5
minutes after the last email.

## Usage

```bash
applytrail            # sync new mail, save, print the table and a summary line
applytrail --offline  # print the saved table; no network, no Gmail, no Ollama
applytrail check acme # have I applied to Acme? (saved data only)
applytrail open 3     # open row 3's email thread in Gmail
applytrail --version
applytrail --help
```

The first sync looks back about six months. With a local model each email takes a few seconds,
so a large first sync can take a while. Ctrl-C is safe: progress is saved and the next run
continues where it stopped.

`applytrail --offline` prints the saved table followed by the time of the last sync, for example
`Last sync: 2026-10-14 08:02 (complete)`. If nothing has been synced yet, it prints
`No data yet. Run applytrail to sync.`

### Check a company

```bash
applytrail check acme
applytrail check "Acme, Inc."
```

`check NAME...` searches the saved applications by company name. Case, punctuation and endings
such as "Inc." or "GmbH" are ignored, and the last word may be the start of a name (`glob` finds
Globex). Every match is listed with its row number, first-seen date, role, status and last-seen
date. When nothing matches, it says so, suggests close names (`Did you mean: Google (#2)?`) and
shows the time of the last sync. `check` reads only the saved data: it needs no network, Gmail or
Ollama, and never changes the data.

### Open an email thread

```bash
applytrail open 3            # by row number from the table
applytrail open acme         # by company name, if only one application matches
applytrail open 3 --print    # print the address only; don't start a browser
```

`open TARGET...` opens the application's Gmail thread in a new browser tab. It always prints
which application it opens, for example `Opening Acme Inc. — Backend Engineer (#1)`, followed by
the address. Row numbers follow the newest-first order, so they can change after a sync; run
`applytrail --offline` or `applytrail check` to see the current numbers. If a name matches
several applications, `open` lists them and asks for a number.

Over SSH, or on Linux with no display, `open` prints `Address for …` and the address and starts
no browser. If the browser cannot be started, it prints the address and a note.

Links name the Google account the data was synced from; each sync asks Gmail which account the
token belongs to. Use a browser signed in to that one Google account. With several accounts
signed in, Gmail can show an "account temporarily unavailable" page instead of the email.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `APPLYTRAIL_HOME` | `~/.applytrail` | Data folder: store, token, credentials |
| `APPLYTRAIL_MODEL` | `qwen3:4b` | Ollama model tag used for extraction |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server (Ollama's own variable). A non-loopback host prints a privacy warning |
| `APPLYTRAIL_DEBUG` | unset | `1` writes tracebacks (frames and exception types, no messages) to `$APPLYTRAIL_HOME/debug.log` |

A `.env` file in the current directory is loaded if present.

## Exit codes

Expected failures print one line to stderr, never a stack trace.

| Code | Meaning |
|---|---|
| 0 | Success, including "nothing new" and `--offline` with no saved data |
| 1 | Unexpected error (set `APPLYTRAIL_DEBUG=1` for a debug log) |
| 2 | Setup needed: Gmail access missing or expired (run `applytrail-auth`), Ollama not running, or the model is not pulled |
| 3 | Cannot reach Gmail; use `applytrail --offline` to view saved data |
| 4 | Ollama stopped responding, Gmail rate limit, or not enough memory for the model; progress is saved |
| 5 | The data file cannot be read; move it aside and run `applytrail` to rebuild |
| 130 | Interrupted with Ctrl-C; progress is saved |

`applytrail check` and `applytrail open` use their own codes:

| Code | Meaning |
|---|---|
| 0 | `check`: found. `open`: the address was printed (and the browser started, unless it could not be) |
| 2 | The input needs fixing: an empty name, a row number out of range, or (`open`) several matches |
| 5 | The data file cannot be read |
| 6 | No matching application, or no data yet |

`applytrail-auth` exits 0 when the token is saved, 2 when `credentials.json` is missing, and 1
when sign-in does not complete.

## Privacy

- Email text is processed only by the local Ollama model. It leaves your machine only if you
  point `OLLAMA_HOST` at another computer; ApplyTrail prints a warning when that host is not
  local.
- Email bodies are never stored or logged. For each application the store keeps the extracted
  company, role, status and dates, the Gmail message and thread IDs, the subject line, and a
  short evidence quote from the model (both capped at 200 characters).
- Email content is treated as untrusted data: nothing in an email can choose an action, run
  code or fetch a URL.
- Everything lives in `~/.applytrail` (or `$APPLYTRAIL_HOME`), a folder with mode `0700`:

  | File | Contents |
  |---|---|
  | `credentials.json` | Your Google OAuth client (you put it there) |
  | `token.json` | Gmail read-only access token, mode `0600` |
  | `applications.json` | Saved applications and sync checkpoint, mode `0600` |
  | `debug.log` | Only with `APPLYTRAIL_DEBUG=1`; tracebacks without messages |

  Delete the folder to remove all ApplyTrail data. To revoke Gmail access, remove ApplyTrail
  from [your Google account's third-party access](https://myaccount.google.com/permissions).

## Using the MCP server on its own

`applytrail-mcp` is a read-only Gmail MCP server on stdio. `applytrail` starts it for you, but
any MCP client can use it. It offers three read-only tools: `search_job_emails`, `get_email`, and
`get_account` (the address of the signed-in Gmail account, used for links). It uses the
same `token.json`, so run `applytrail-auth` first.

Try it with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector applytrail-mcp
```

Or, without Node, with the FastMCP CLI that ships with ApplyTrail (from a source checkout,
prefix `uv run`):

```bash
fastmcp list --command "applytrail-mcp" --input-schema --output-schema
fastmcp call --command "env APPLYTRAIL_HOME=$HOME/.applytrail applytrail-mcp" \
  --target search_job_emails --input-json '{"after": "2026-10-01T00:00:00Z"}'
```

The `fastmcp` CLI does not pass your shell's environment to the server, so set
`APPLYTRAIL_HOME` inside `--command` as shown. Otherwise the server uses the default
`~/.applytrail`.

Or add it to Claude Desktop's `claude_desktop_config.json` (use the full path that
`which applytrail-mcp` prints):

```json
{
  "mcpServers": {
    "applytrail-gmail": {
      "command": "/Users/you/.local/bin/applytrail-mcp",
      "env": { "APPLYTRAIL_HOME": "/Users/you/.applytrail" }
    }
  }
}
```

Email text returned by these tools goes to whichever model the client uses, so the
local-only guarantee above applies to `applytrail` itself, not to other MCP clients.

## Development

```bash
uv sync                                               # install with dev tools
uv run pytest                                         # tests (never call Gmail or a live model)
uv run ruff check . && uv run ruff format --check .   # lint and format
uv run python scripts/eval_extractor.py               # golden-set eval (needs Ollama)
```

See `AGENTS.md` for project rules and `specs/001-gmail-sync-table/` for the design.
