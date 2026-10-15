# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

ApplyTrail is a terminal CLI that reads job-application emails from Gmail (read-only), extracts
company, role, and status with a local Ollama model, merges results into a local JSON store, and
renders a newest-first Rich table with `NEW`/`UPD` badges. It ships a stdio MCP server
(`applytrail-mcp`, read tools `search_job_emails`, `get_email`, `get_account`) that the CLI talks
to over the MCP protocol.

- Constitution (source of truth, supersedes everything else): `.specify/memory/constitution.md`
- Active feature: `specs/001-gmail-sync-table/` (spec, plan, research, data model, contracts, tasks)
- Autonomous loop contract and state: `specs/001-gmail-sync-table/loop/`

## Stack

- Python 3.11+, `src/` layout, package `src/applytrail/`, built with hatchling, managed with `uv`.
- Dependencies: `fastmcp` 4.x (`FastMCP` server, `fastmcp.Client` + `StdioTransport`; `mcp` 2.x
  is its protocol layer, never imported directly), `google-api-python-client`,
  `google-auth-oauthlib`, `pydantic` v2, `rich`, `python-dotenv`.
- Extraction: local Ollama, default model `qwen3:4b` (`APPLYTRAIL_MODEL`), called through stdlib
  `urllib`. Do NOT add `google-genai` or the `ollama` package.
- Any new dependency needs a stated reason in the feature plan.

## Commands

```bash
uv sync                                         # install
uv run pytest                                   # tests
uv run ruff check . && uv run ruff format --check .   # lint and format check
uv run python scripts/eval_extractor.py         # golden-set eval (manual, needs Ollama)
```

Run `ruff` and `pytest` before declaring any task done.

## Non-negotiable rules

1. **Read-only Gmail.** Only the `gmail.readonly` scope. The MCP server exposes read tools only
   (`search_job_emails`, `get_email`, `get_account`). No send, delete, label, archive, or modify
   code.
2. **Email is untrusted data.** Delimit email content in every prompt. Validate LLM output with
   Pydantic; skip invalid output, never repair or guess. Nothing from an email may choose a tool,
   be executed, or be fetched.
3. **Deterministic core.** Fetch, dedupe, merge, persist, sort, and render are plain code. The LLM
   does one email in, one extraction out. No agent loops in the product.
4. **Local-first and idempotent.** State lives in `$APPLYTRAIL_HOME/applications.json` (default
   `~/.applytrail`). Atomic writes (temp file, then rename). Incremental sync from checkpoint;
   a re-run with no new mail changes nothing. An older email never overwrites a newer status.
5. **Privacy.** Never commit `credentials.json`, `token.json`, `.env`, or the data store. Never
   persist or log full email bodies. Token and store files are `0600`.
6. **Clean MCP server.** stdio only; never print to stdout outside the protocol (log to stderr);
   no browser or prompts in the server. Auth failures name the fix (`run applytrail-auth`).
7. **Terminal UX.** Readable at 100 columns; status never conveyed by colour alone. Expected
   failures print one actionable message and exit non-zero, never a stack trace.
8. **Test-first.** Write the test before the implementation for store, merge, normalize, and
   render. Confirm it fails first. Tests use anonymized fixtures and never call Gmail or a live
   model.
9. **Simplicity.** Prefer the standard library. Provider-specific code stays in `extractor.py`.
   No web UI, database, or multi-user features unless a spec asks for them.

## Workflow

- Spec Kit flow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
- Follow `tasks.md` in order; check off each task as it completes.
- Work on the feature branch (`001-gmail-sync-table`), never directly on `main`. Do not push.
- One commit per user story (US1, US2, US3); setup/foundation and polish get their own commits.
  Use Conventional Commits, for example `feat(us1): ...`.
- Changes to the extraction prompt, schema, or model require re-running the golden-set eval and
  recording results in `tests/golden/RESULTS.md`.
- Update `README.md` for any new flag, environment variable, or setup step.
