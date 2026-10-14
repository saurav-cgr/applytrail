# Research: Gmail Sync and Application Table

**Feature**: `001-gmail-sync-table` | **Date**: 2026-10-14

Each entry records a decision, why it was made, and what else was considered.

## R1. MCP SDK version and server API

- **Decision**: Use `mcp` 2.x (latest on PyPI: 2.3.0). The server class is `MCPServer`
  (`from mcp.server import MCPServer`), tools are registered with `@server.tool()`, and the CLI
  connects with `mcp.Client` over stdio using `StdioServerParameters`. Tests connect `Client`
  directly to the `MCPServer` instance in-process, so no subprocess and no network is needed.
- **Rationale**: v2 is the current stable line. Tool results expose `structured_content` and
  `is_error`, which lets the CLI read typed results and surface auth errors cleanly (Principle VI).
  The in-process client makes MCP contract tests cheap.
- **Alternatives considered**: Pin `mcp<2` to keep the `FastMCP` class named in the constitution and
  Python 3.10 support. Rejected: it locks the project to a superseded line on day one.
- **Consequence**: `mcp` 2.x requires Python 3.11+. The constitution says Python ≥ 3.10 and names
  "FastMCP". See Complexity Tracking in `plan.md`; a PATCH amendment is recommended.

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
  (12), Last activity (10, `YYYY-MM-DD`). Overflow is ellipsized. Company cells use
  `[link=https://mail.google.com/mail/u/0/#all/<thread_id>]` markup; Rich drops links on terminals
  that do not support them. Status is always text; colour only reinforces it.
- **Rationale**: Fits 100 columns with borders (FR-013); Rich already in the dependency set.
- **Alternatives considered**: Plain `str.format` table (no hyperlinks, more code).

## R10. Testing and golden-set evaluation

- **Decision**: `pytest` unit tests for normalize, merge, store, sync orchestration (with a fake
  MCP client and fake extractor), render (Rich console recording at width 100), and CLI error
  mapping. MCP contract tests run the real `MCPServer` in-process with a fake Gmail service. The
  golden set lives in `tests/golden/` as anonymized `.eml`-like JSON plus expected labels;
  `scripts/eval_extractor.py` runs it against the live model and prints accuracy. CI never runs it.
- **Rationale**: Principle VIII.
