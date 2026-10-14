# ApplyTrail Constitution

A terminal application that reads job-application emails from Gmail through a project-owned MCP
server, extracts company, role and status with an LLM, stores results locally, and renders a
newest-first table in the terminal.

## Core Principles

### I. Least-Privilege, Read-Only Access

- The application MUST request only the `gmail.readonly` OAuth scope.
- The MCP server MUST expose only read tools. Tools that send, delete, label, archive, or modify
  mail MUST NOT exist.
- Adding any OAuth scope or any write-capable tool requires a MAJOR constitution amendment.

**Rationale:** The tool processes untrusted email. Read-only access bounds the damage of any bug or
injection to a wrong row in a local file.

### II. Email Content Is Untrusted Data

- Email subjects, senders, and bodies MUST be treated as data, never as instructions. They MUST be
  delimited as such in every LLM prompt.
- LLM output MUST be validated against a typed schema (Pydantic). Output that fails validation, has
  an unknown status, or has an empty company MUST be skipped, never guessed or repaired.
- Nothing derived from email content may be executed, fetched, or used to choose which tool to call.

**Rationale:** Prompt injection via email is the primary threat model.

### III. Deterministic Core, LLM at the Edge

- Fetching, deduplication, merging, persistence, sorting, and rendering MUST be deterministic,
  plain code.
- The LLM is confined to a single responsibility: one email in, one structured extraction out.
- Agent loops or LLM-driven tool selection MUST NOT be introduced without a written justification
  in the feature plan showing what deterministic code cannot do.

**Rationale:** This keeps behaviour predictable, testable, and cheap, and leaves the LLM doing only
the judgment it is needed for.

### IV. Local-First, Incremental, Idempotent

- All state lives in a local JSON store under `APPLYTRAIL_HOME` (default `~/.applytrail`).
  There is no hosted backend.
- Each sync MUST fetch only messages since the last checkpoint (with a small overlap) and skip
  already-processed message IDs.
- Re-running a sync with no new mail MUST leave the stored applications unchanged.
- Writes MUST be atomic (write to a temp file, then rename). Progress MUST be persisted during long
  syncs so that a crash never forces a full re-scan.
- An email older than an application's last update MUST NOT overwrite its status.

### V. Privacy and Secret Hygiene

- `credentials.json`, `token.json`, `.env`, and the data store MUST be git-ignored. Token files
  MUST be written with owner-only permissions.
- Full email bodies MUST NOT be persisted or logged. The store keeps only the subject, extracted
  fields, a short evidence string, and IDs.
- Email bodies are sent only to the configured LLM provider, and are truncated to a bounded length.
- The README MUST state which provider receives email content and the provider's data-use terms
  (for example, whether the free tier may be used for training).

### VI. Clean MCP Contract

- The MCP server runs over stdio. It MUST NOT write to stdout outside the protocol, and MUST NOT
  perform interactive actions such as opening a browser or prompting.
- Tools MUST be task-shaped, typed, and documented with docstrings that are sufficient for any MCP
  client.
- The server MUST be usable on its own from MCP Inspector or Claude Desktop, independent of the CLI.
- Authentication failures MUST surface as clear tool errors naming the fix (for example, "run
  `applytrail-auth`").

### VII. Terminal-First User Experience

- The default command syncs, then renders. `--offline` renders from the store with no network
  access.
- Rows are ordered newest activity first. Entries added or changed in the latest sync carry a
  visible `NEW` or `UPD` badge.
- Output MUST stay readable at 100 columns, MUST NOT rely on colour alone to convey status, and
  SHOULD link each company to its Gmail thread where the terminal supports hyperlinks.
- Expected failures (missing token, missing API key, rate limit, offline) MUST print one actionable
  message and a non-zero exit code, never a stack trace.

### VIII. Test-First for Deterministic Code

- Store, merge, normalization, and rendering logic MUST have unit tests written before or alongside
  implementation.
- Tests MUST use anonymized email fixtures. CI MUST NOT call Gmail or a live LLM.
- The extractor is evaluated against a small labelled golden set of anonymized emails. Changing the
  model or prompt requires re-running that evaluation and recording the accuracy in the PR.

### IX. Simplicity and Replaceability

- Prefer the standard library and the existing dependency set. A new dependency requires a stated
  reason in the plan.
- The LLM model MUST be configurable via environment variable. Provider-specific code MUST stay
  behind the extractor interface so the provider can be swapped without touching other modules.
- YAGNI: no web UI, database, or multi-user features unless specified by a feature spec.

## Technical Constraints

- **Language:** Python ≥ 3.10, packaged with `pyproject.toml`, installed via `uv` or `pipx`.
- **Core dependencies:** `mcp` (FastMCP server and stdio client), `google-api-python-client`,
  `google-auth-oauthlib`, `google-genai`, `pydantic`, `rich`, `python-dotenv`.
- **Default model:** `gemini-3.1-flash-lite`, overridable via `APPLYTRAIL_MODEL`.
- **Authentication:** Google OAuth Desktop-app flow. One-time login via `applytrail-auth`;
  refresh is silent afterwards.
- **Tooling:** `ruff` for lint and format, `pytest` for tests.
- **Performance target:** an incremental sync of 20 new emails completes in under 60 seconds on the
  free tier, including rate-limit backoff.

## Development Workflow

- Features follow the Spec Kit flow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`.
- Every plan MUST include a Constitution Check section addressing Principles I–IX. Any deviation is
  listed under Complexity Tracking, together with its justification.
- Every PR MUST:
  - pass `ruff` and `pytest`;
  - update the README for any new flag, environment variable, or setup step;
  - include a golden-set evaluation result if it touches the prompt, schema, or model.
- Commits SHOULD be small and scoped to one task from `tasks.md`.

## Governance

This constitution supersedes conflicting practices, specs, and plans. Amendments are made via PR
that updates this file and the Sync Impact Report, with semantic versioning:

- **MAJOR:** a principle is removed or redefined, or a scope or permission boundary changes
  (Principle I).
- **MINOR:** a principle or section is added, or guidance is materially expanded.
- **PATCH:** clarifications and wording fixes.

Compliance is checked at the plan stage and in PR review.

**Version**: 1.0.0 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-14
