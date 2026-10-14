# Research: Gmail Sync and Application Table

**Feature**: `001-gmail-sync-table` | **Date**: 2026-10-14

Each entry records a decision, why it was made, and what else was considered.

## R1. MCP framework: FastMCP (revised 2026-10-14)

- **Decision**: Build the server and the CLI-side client on the standalone **`fastmcp`** package
  (`fastmcp>=4.1,<5`; 4.1.0 is current on PyPI). It replaces direct use of the `mcp` 2.x SDK
  (`MCPServer`, `mcp.Client`, `StdioServerParameters`).
  - Server: `server = FastMCP("applytrail-gmail", mask_error_details=True)`, tools registered with
    `@server.tool`, run with `server.run("stdio", show_banner=False)`.
  - Tools return the Pydantic models (`SearchPage`, `EmailMeta`) directly. FastMCP derives the
    output schema from the return annotation and fills `structured_content`. The hand-built
    `CallToolResult` wrapping goes away.
  - Expected failures raise `fastmcp.exceptions.ToolError("<PREFIX>: …")`. FastMCP sends the message
    text unchanged with `is_error = true`, so the contract's prefixes are preserved. Unexpected
    exceptions become `Error calling tool '<name>'` with details hidden by `mask_error_details`;
    the client maps that text to `GmailError("unknown")`, as it does today.
  - Client: `fastmcp.Client(StdioTransport(command=sys.executable, args=["-m",
    "applytrail.mcp_server"], env=…))`. Tests pass the `FastMCP` instance to `Client` for an
    in-process session. Calls use `call_tool(..., raise_on_error=False)` so `mcp_client.py` keeps
    the single prefix-to-error mapping.
  - `fastmcp.Client` is async-only, so the anyio blocking portal in `mcp_client.py` stays.
- **Rationale**: The user asked for FastMCP. It is the framework the constitution first named, and
  it is the higher-level API. Verified in a scratch venv against `fastmcp` 4.1.0:
  - `ToolError` text arrives verbatim (no "Error executing tool" prefix). That prefix is the
    reason the current server builds `CallToolResult` by hand, so about 25 lines of
    `_call`/`_error` plumbing go away.
  - Pydantic return types give the same output schema and `structured_content` shape as today.
  - Pydantic `Field` constraints (`ge`/`le`, descriptions) reach the input schema unchanged.
  - Invalid arguments come back as `is_error` results, not exceptions.
  - With `show_banner=False`, the server writes nothing to stdout outside the protocol.
    Tracebacks for unexpected errors go to stderr through Rich logging (Principle VI).
  - `fastmcp` 4.1.0 depends on `mcp==2.3.0` (through `fastmcp-slim`), which is the version locked
    today. The protocol layer does not change.
- **Alternatives considered**:
  - Keep `mcp` 2.x `MCPServer` (current code). Rejected: the user asked to move. It also needs the
    manual `CallToolResult` workaround for error text.
  - `mcp<2` with `mcp.server.fastmcp.FastMCP` (the class bundled in SDK v1). Rejected: superseded
    line. It would also downgrade the protocol library that `fastmcp` 4.x itself requires.
- **Consequences**:
  - Python stays ≥ 3.11. `fastmcp` allows 3.10, but its `mcp` 2.x dependency needs 3.11.
  - The dependency tree is larger: `fastmcp` brings in `httpx`, `cyclopts`, auth and HTTP extras
    that the stdio server does not use. This is accepted for API simplicity. If install size
    matters, `fastmcp-slim[server,client]` is the trimmed alternative; it was not chosen because
    `fastmcp` is what the docs and the user name.
  - `fastmcp.Client.list_tools()` returns a list, not a result object. Tool schema fields are
    `input_schema`/`output_schema` (the camelCase names are deprecated).
  - The constitution's Technical Constraints say "`mcp` 2.x `MCPServer`" and need a PATCH
    amendment to name `fastmcp` (see `plan.md` Complexity Tracking).

## R2. LLM provider and structured output

- **Decision**: Local inference through **Ollama** (already installed on the developer machine,
  v0.32). The model is **`qwen3:4b`** (Q4, about 2.5 GB on disk and about 3 GB RAM when loaded),
  overridable with `APPLYTRAIL_MODEL`. `OllamaExtractor` calls `POST {OLLAMA_HOST}/api/chat`
  through stdlib `urllib.request`, so no new dependency is added. The request body is:

  ```json
  {
    "model": "qwen3:4b",
    "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "<email>…</email>"}],
    "format": {"…": "Extraction.model_json_schema()"},
    "think": false,
    "stream": false,
    "keep_alive": "5m",
    "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 256}
  }
  ```

  The code reads `message.content` and validates it with `Extraction.model_validate_json`.
- **Rationale**:
  - No rate limits or quotas. This removes the whole free-tier design (limiter, 429
    classification, multi-day first runs).
  - Email content never leaves the machine (Principle V, at its strongest).
  - No API key to manage.
  - JSON-schema `format` constrains decoding to the schema. Pydantic validation is still required
    (Principle II), because the schema constrains shape, not truth.
  - `think: false` turns off Qwen3's reasoning mode. Reasoning would add hundreds of output tokens
    per email for little gain on a single-label extraction.
  - `num_ctx: 4096` is set explicitly so the prompt is never silently truncated. The system prompt
    is about 400 tokens and a 4,000-character body is about 1,000 tokens, so the prompt fits.
  - `num_predict: 256` bounds runaway output.
- **Alternatives considered**:
  - Gemini free tier (earlier draft). Rejected: unpublished, shifting quotas (15–30 RPM,
    500–1,500 RPD reported) forced extra complexity, and email text left the machine.
  - `ollama` Python package. Rejected: the stdlib covers one POST and one GET (Principle IX).
  - Hugging Face `transformers` or `mlx-lm` in-process. Rejected: heavy dependencies (torch or
    mlx), plus manual model download and chat templating. Ollama already manages these.
  - Larger models (7–8B, about 5–6 GB RAM). Not the default because of memory pressure on a 16 GB
    laptop with a browser and IDE open. Use one if the golden set misses the target (R3).
  - Function calling or tools. Rejected: Principle III.

## R3. Local model: resources, speed, and accuracy

**Hardware baseline**: Apple M1 Pro, 16 GB unified memory.

- **Memory**: `qwen3:4b` Q4 uses about 3 GB while loaded. With `keep_alive: "5m"`, Ollama unloads
  it 5 minutes after the last request, so RAM is used only during and just after a sync.
  Requests are sequential, which keeps one KV cache and avoids extra memory from parallel slots.
- **Speed (estimate; measured in quickstart)**:
  - Cold model load is about 3–8 s, once per run.
  - Per email: prompt evaluation of about 1.4k tokens plus about 60–80 output tokens takes roughly
    2–3.5 s.
  - The system prompt is a fixed, identical prefix, so Ollama can reuse its cache across calls.
  - Estimate for 20 emails: about 45–75 s. SC-001 (< 60 s) is likely but not guaranteed.
  - Mitigations, in order: lower the body cap from 4,000 to 3,000 characters, and keep the
    `evidence` instruction short (≤ 120 characters) to reduce output tokens.
  - First run (a few hundred candidates): about 10–25 min, with no quota interruption.
- **Accuracy**: unknown until measured. Run `scripts/eval_extractor.py` on the golden set before
  building the rest of the pipeline on top (first extractor task).
  - Target is SC-003: ≥ 90% company and status accuracy, and zero rows from non-job emails.
  - If the target is missed, try these in order: a prompt tweak; `gemma3:4b`; `qwen3:8b`
    (about 5.5 GB RAM). Record each result in the PR (Principle VIII).
- **Concurrency**: none. Parallel requests would multiply KV-cache memory on a 16 GB machine,
  and a single local model gains little from them.
- **Remote host risk**: `OLLAMA_HOST` (Ollama's own variable, default `http://127.0.0.1:11434`)
  can point at another machine. Email text would then leave the laptop. The code allows this but
  prints one stderr warning when the host is not loopback, and the README says the same.

## R4. Reducing what reaches the LLM

- **Decision**: Two deterministic filters before extraction:
  1. Gmail search query: `after:<epoch> -in:chats -in:sent -in:drafts -category:promotions` combined
     with an OR of job-related terms and common applicant-tracking sender domains (Greenhouse,
     Lever, Workday, Ashby, SmartRecruiters, iCIMS, Workable, Jobvite, Teamtailor).
     The query lives in one constant in `gmail_client.py`.
  2. Skip messages whose ID is already in the processed set.
  The LLM then classifies the remainder; non-job results are recorded as `ignored`.
- **Rationale**: The first run covers 6 months. Without a pre-filter, local extraction time grows
  with every newsletter. Search-side filtering costs nothing.
- **Alternatives considered**: Send every message to the LLM (time cost); a hand-written
  classifier (brittle, and the LLM is already needed for extraction).
- **Risk**: The query can miss an application email that uses none of the terms. Accepted for v1;
  the golden set should include a few unusual phrasings to measure it.

## R5. Incremental sync and checkpoint semantics

- **Decision**: `sync_state.checkpoint` is a UTC timestamp. A sync searches
  `after:(checkpoint − 1 hour)`; the overlap catches clock skew and late-indexed mail. Messages are
  processed newest first (see below). The processed-ID set prevents double work. The checkpoint advances to
  the newest processed email's date only when the whole result list has been handled; on a crash
  or extractor failure the checkpoint is not advanced, and the next run re-lists the same window but skips
  processed IDs (SC-005).
- **Processing order: newest first.** A long first run (10–25 min) may be interrupted. Newest-first
  means an interruption still leaves the most recent, most useful applications. Order does
  not affect correctness:
  - the processed-ID set governs what is skipped;
  - the checkpoint only advances after a complete run;
  - merge guards on date (an older email never overwrites a newer status, and `first_seen` takes
    the minimum).
  
  One exception is the role-missing merge rule ("the company has exactly one application"), which
  can resolve differently depending on order. Accepted: when ambiguous it produces a `role:
  Unknown` row, never a wrong status.
- **First run**: no checkpoint, so the window starts at now − 182 days (6 months).
- **Rationale**: Deterministic, idempotent, and needs no Gmail history API.
- **Alternatives considered**: Gmail `historyId` incremental sync. Rejected: history IDs expire
  after about a week of inactivity, requiring a fallback path anyway.

## R6. Local store format and atomic writes

- **Decision**: One JSON file, `$APPLYTRAIL_HOME/applications.json` (default `~/.applytrail`), with
  a `schema_version` field. Write to `applications.json.tmp` in the same directory, `fsync`, then
  `os.replace`. Directory created with mode 0700. Progress saved every 10 processed emails and at
  the end. If the file exists but cannot be parsed or fails validation, abort with a message naming
  the file; never overwrite it.
- **Rationale**: Human-readable (spec FR-015), atomic on POSIX, standard library only.
- **Alternatives considered**: SQLite (Principle IX: no database); JSON Lines append log (harder to
  read and merge by hand).

## R7. Gmail authentication

- **Decision**: `google-auth-oauthlib` `InstalledAppFlow.from_client_secrets_file(credentials.json,
  scopes=["https://www.googleapis.com/auth/gmail.readonly"]).run_local_server(port=0)` in
  `applytrail-auth` only. Token saved to `$APPLYTRAIL_HOME/token.json` with mode 0600. The MCP
  server only loads and refreshes the token; if missing, invalid, or the refresh fails, the tool
  returns an error naming `applytrail-auth`.
- **Rationale**: Principle I (single read-only scope) and Principle VI (server never opens a browser).
- **Alternatives considered**: Running the browser flow from the server on first use. Rejected by
  Principle VI.

## R8. Company and role normalization

- **Decision**: Key = normalized company + "|" + normalized role. Company: casefold, replace `&`
  with `and`, strip punctuation, drop trailing legal suffixes (`inc`, `incorporated`, `llc`,
  `ltd`, `limited`, `corp`, `corporation`, `co`, `company`, `gmbh`, `plc`, `pvt`, `private`, `sa`,
  `ag`, `bv`), collapse whitespace. Role: casefold, collapse whitespace, strip punctuation at ends.
  Display uses the most recent original spelling.
- **Rationale**: Covers the spec example ("Acme", "ACME Inc.", "Acme Corporation"), deterministic,
  unit-testable.
- **Alternatives considered**: Asking the LLM to canonicalize (non-deterministic, Principle III);
  fuzzy matching (false merges between different companies).

## R9. Terminal rendering

- **Decision**: `rich.table.Table` with columns: badge (4), Company (≤ 28), Role (≤ 30), Status
  (12), Last seen (10, `YYYY-MM-DD`). Overflow is ellipsized. Company cells use
  `[link=https://mail.google.com/mail/u/0/#all/<thread_id>]` markup; Rich drops links on terminals
  that do not support them. Status is always text; colour only reinforces it.
- **Rationale**: Fits 100 columns with borders (FR-013); Rich already in the dependency set.
- **Alternatives considered**: Plain `str.format` table (no hyperlinks, more code).

## R10. Testing and golden-set evaluation

- **Decision**: `pytest` unit tests for normalize, merge, store, sync orchestration (with a fake
  MCP client and fake extractor), render (Rich console recording at width 100), and CLI error
  mapping. MCP contract tests run the real `FastMCP` server in-process (`fastmcp.Client(server)`)
  with a fake Gmail service. The golden set lives in `tests/golden/` as anonymized `.eml`-like JSON plus expected labels;
  `scripts/eval_extractor.py` runs it against the live model and prints accuracy. CI never runs it.
- **Rationale**: Principle VIII.
