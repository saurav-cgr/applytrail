# Implementation Plan: Gmail Sync and Application Table

**Branch**: `001-gmail-sync-table` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-gmail-sync-table/spec.md`

## Summary

`applytrail` lists likely job-application emails since the last checkpoint through a project-owned,
read-only **FastMCP** server over stdio, sends each new email (truncated, delimited as untrusted data) to a
**local Ollama model (`qwen3:4b`)** for one schema-validated extraction, merges results deterministically into a local JSON
store, and renders a newest-first Rich table with `NEW`/`UPD` badges. `--offline` renders from the
store only.

Local inference replaces the earlier Gemini free-tier design. It removes rate limits, quotas and
the API key, and email text never leaves the machine. The trade-offs are a one-time `ollama pull`,
about 3 GB of RAM during a sync (unloaded after 5 min idle), and accuracy that must be proven on the
golden set before the rest is built on it. A preflight checks that Ollama is running and the model is
installed before any Gmail call. Emails are processed newest first, so an interrupted long first run
still shows the most relevant applications. Design decisions: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (developer machine has 3.14)

**Primary Dependencies**: `fastmcp` 4.x (`FastMCP` server, `fastmcp.Client` + `StdioTransport`;
pulls in `mcp` 2.3 as its protocol layer), `google-api-python-client`,
`google-auth-oauthlib`, `pydantic` v2, `rich`, `python-dotenv`. Ollama is reached through stdlib
`urllib`, so no client library is needed. External runtime: Ollama ≥ 0.9 (`think` and JSON-schema
`format`); the dev machine has 0.32

**Storage**: Single JSON file `$APPLYTRAIL_HOME/applications.json`, atomic replace
([contracts/store-schema.md](contracts/store-schema.md))

**Testing**: `pytest`; `ruff` lint/format; in-process `fastmcp.Client(server)` for contract tests; golden-set
script for the extractor (not in CI)

**Target Platform**: macOS and Linux terminals. Reference machine: M1 Pro, 16 GB

**Project Type**: CLI tool plus a stdio MCP server (FastMCP) in one package

**Performance Goals**: 20 emails in < 60 s (SC-001). Estimate is 2–3.5 s per email plus 3–8 s
cold load, so 45–75 s; measured in quickstart Scenario 3b, with mitigations in R3;
`--offline` render of 500 applications in < 2 s

**Constraints**: 16 GB RAM shared with browser and IDE, so a ≤ 4B Q4 model (about 3 GB), sequential
requests, `num_ctx` 4096; `gmail.readonly` only; no
email bodies persisted; table ≤ 100 columns

**Scale/Scope**: One user, one mailbox; first run covers 6 months (hundreds of candidate emails
after pre-filtering; about 10–25 min locally, no quota); store up to a few thousand processed IDs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How the design complies |
|---|---|---|
| I. Least-privilege, read-only | PASS | Only `gmail.readonly` requested in `applytrail-auth`; MCP exposes `search_job_emails` and `get_email` only ([mcp-tools.md](contracts/mcp-tools.md)) |
| II. Email is untrusted data | PASS | `<email>` delimiters, `</email>` escaping, fixed system instruction; Pydantic validation; invalid/incomplete → skipped; tool calls are chosen by code, never by email content ([extraction.md](contracts/extraction.md)) |
| III. Deterministic core | PASS | Search, dedupe, merge, persistence, sort, render are plain code; LLM does one email → one extraction; no agent loop |
| IV. Local-first, incremental, idempotent | PASS | JSON store under `APPLYTRAIL_HOME`; checkpoint − 1 h overlap + processed-ID set; atomic writes; save every 10 emails; older email never overwrites status (R5, R6, merge rules). Extractor failures and Ctrl-C save progress and leave the checkpoint unadvanced, so the next run resumes |
| V. Privacy and secret hygiene | PASS | `.gitignore` covers secrets and data; token and store 0600, folder 0700; bodies never stored or logged; body truncated to 4,000 chars. Extraction is local (Ollama), so email text leaves the machine only if the user points `OLLAMA_HOST` at another host, which prints a warning. README states this |
| VI. Clean MCP contract | PASS | stdio via `server.run("stdio", show_banner=False)`; no stdout prints (FastMCP logs to stderr); no browser in server; typed Pydantic returns give output schemas; docstrings become tool descriptions; `ToolError("AUTH_REQUIRED: …")` names `applytrail-auth` verbatim; unexpected errors masked (`mask_error_details=True`); usable from MCP Inspector and `fastmcp list` |
| VII. Terminal-first UX | PASS | Default syncs then renders; `--offline`; newest first; text badges and status; ≤ 100 columns; hyperlinks; one-line errors with exit codes ([cli.md](contracts/cli.md)). Preflight errors name the fix (`ollama serve`, `ollama pull <model>`); an extractor failure mid-run still prints the saved table plus a resume message |
| VIII. Test-first | PASS | Unit tests precede store/merge/normalize/render code in tasks; anonymized fixtures; no live calls in CI; golden-set script |
| IX. Simplicity and replaceability | PASS with note | `google-genai` dropped (stdlib HTTP); `APPLYTRAIL_MODEL`; Ollama code only in `extractor.py`. FastMCP removes the manual `CallToolResult`/error plumbing in `mcp_server.py`; MCP code stays in `mcp_server.py` and `mcp_client.py`. Note: `fastmcp` adds transitive packages (httpx, cyclopts, auth extras) unused by a stdio server — see Complexity Tracking |
| Technical Constraints | DEVIATION | The constitution says "`mcp` 2.x (`MCPServer` and stdio client)"; this plan uses `fastmcp` 4.x (on top of `mcp` 2.3). Needs a PATCH amendment. Earlier deviations (Python 3.11, Ollama) are already ratified. Justified below |

**Post-design re-check (after Phase 1, FastMCP revision 2026-10-14)**: all principles still PASS.
The wire contract (tool names, schemas, `structured_content`, error texts) is unchanged, so the CLI,
sync, store, and render are untouched. Only `mcp_server.py`, `mcp_client.py`, their tests,
`pyproject.toml`/`uv.lock`, README and AGENTS.md change. Deviation: Technical Constraints only
(dependency name).

**Earlier re-check (Ollama revision)**: all principles still PASS. Principle V
is stronger: no third-party processing. Deviations are limited to Technical Constraints: versions,
provider and default model, and the performance target wording.

## Project Structure

### Documentation (this feature)

```text
specs/001-gmail-sync-table/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── cli.md
│   ├── mcp-tools.md
│   ├── store-schema.md
│   └── extraction.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 ($speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml           # entry points: applytrail, applytrail-auth, applytrail-mcp
README.md
.gitignore
src/applytrail/
├── __init__.py
├── config.py            # env vars, paths, defaults
├── models.py            # Status, Extraction, EmailMeta, Application, ProcessedEmail, SyncState, Store
├── normalize.py         # company/role keys
├── store.py             # load/validate, atomic save, permissions
├── merge.py             # apply extraction → application; badge tracking
├── extractor.py         # Extractor protocol, OllamaExtractor (stdlib HTTP), preflight, prompt, errors
├── gmail_auth.py        # OAuth flow (applytrail-auth), token load/refresh
├── gmail_client.py      # Gmail API calls, search query constant, body-to-text
├── mcp_server.py        # FastMCP server + two tools, ToolError mapping (applytrail-mcp)
├── mcp_client.py        # fastmcp.Client over StdioTransport, typed wrappers, error mapping
├── sync.py              # orchestration: search → filter → extract → merge → save
├── render.py            # Rich table + summary line
├── errors.py            # typed errors → exit codes/messages
└── cli.py               # argparse, .env loading, main()

tests/
├── fixtures/            # anonymized email JSON
├── golden/              # labelled anonymized emails for eval script
├── unit/                # normalize, merge, store, render, extractor prompt/validation/error
│                        # mapping (fake HTTP), cli errors
├── contract/            # MCP tools via in-process fastmcp.Client + fake Gmail service
└── integration/         # sync end-to-end with fake MCP client + fake extractor

scripts/
└── eval_extractor.py    # live golden-set accuracy (manual)
```

**Structure Decision**: Single Python package with `src/` layout. The MCP server and CLI ship
together but meet only through the MCP protocol, so the server stays usable on its own.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Python 3.11+ instead of ≥ 3.10 | `fastmcp` 4.x depends on `mcp` 2.x, which requires 3.11 | Pinning `mcp<2` locks the project to a superseded SDK |
| `fastmcp` 4.x instead of constitution's "`mcp` 2.x `MCPServer`" | User request; `ToolError` passes contract error text verbatim, Pydantic returns give structured output, so ~25 lines of `CallToolResult` plumbing go away | Keep `MCPServer`: works, but needs manual result building to avoid the SDK's "Error executing tool" prefix. `fastmcp-slim[server,client]`: smaller install, but less familiar name; revisit if install size matters |
| Local Ollama instead of `google-genai` + `gemini-3.1-flash-lite` (constitution Technical Constraints) | Free-tier quotas are unpublished and as low as 15 RPM / 500 RPD, which forced a limiter, 429 classification and multi-day first runs. Local inference removes all of it and keeps email on-device | Gemini free tier (complexity, privacy); paid Gemini (cost, still third-party); HF `transformers`/`mlx-lm` (heavy dependencies) |
| Perf target "20 emails < 60 s on the free tier" now depends on local hardware | The estimate on an M1 Pro is 45–75 s; not guaranteed | Bigger hardware is out of scope. Mitigations: smaller body cap, shorter evidence quote. Measured in quickstart Scenario 3b |

### FastMCP migration scope (revision 2026-10-14)

Implementation is complete on this branch with `mcp` 2.x. The migration is a contained swap:

1. `pyproject.toml`: `mcp>=2.3,<3` → `fastmcp>=4.1,<5`; `uv lock`.
2. `mcp_server.py`: `FastMCP("applytrail-gmail", mask_error_details=True)`; `@server.tool`; tools
   return `SearchPage`/`EmailMeta`; `_call` maps Gmail errors to `ToolError` with the same
   prefixes (no `CallToolResult` building); `main()` runs `server.run("stdio", show_banner=False)`.
3. `mcp_client.py`: `fastmcp.Client`; `server_parameters()` returns `StdioTransport` (same
   command/args/env); `call_tool(..., raise_on_error=False)`; `_error_from_text` unchanged (also
   handles `Error calling tool '…'` → `GmailError("unknown")`).
4. Tests: swap imports (`fastmcp.Client`, `StdioTransport`); `list_tools()` returns a list. The
   contract assertions stay the same; that is the parity proof.
5. Docs: README, AGENTS.md, tasks.md history note; constitution PATCH.

Validation: [quickstart.md](quickstart.md) Scenarios 6 and 7.

Recommended follow-ups (not done by this command):
- **PATCH** constitution amendment: Technical Constraints "`mcp` 2.x (`MCPServer` and stdio
  client)" → "`fastmcp` 4.x (`FastMCP` server and client; `mcp` 2.x protocol layer)".
- Earlier (already ratified) **MINOR** amendment to Technical Constraints:
  - Python ≥ 3.11 and `mcp` 2.x `MCPServer`.
  - Replace `google-genai` with "local Ollama over HTTP (stdlib)" and set the default model to
    `qwen3:4b`.
  - Restate the performance target as "20 emails < 60 s on the reference laptop".
  - Principle V: the README states extraction is local, plus the `OLLAMA_HOST` caveat.
- Spec edits (`/speckit-specify` or a manual edit), since the spec still assumes a hosted service:
  - Edge case "Extraction service key missing" becomes "Ollama not running / model not
    installed".
  - Edge case "Rate limit reached" applies to Gmail only.
  - Assumption "sent to one configured third-party extraction service" becomes "processed by a
    local model".
  - FR-020's list of expected failures changes to match.
- **Gate before building on the extractor:** run the golden-set evaluation with `qwen3:4b`. If it
  scores below 90%, try `gemma3:4b`, then `qwen3:8b`.
