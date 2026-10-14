# Loop Memory

Conventions, decisions, and dead ends that should survive between runs so the
loop never re-derives or re-litigates them. Keep entries short and durable.

- [M-001] One git commit per user story (US1, US2, US3); foundation and polish get their own commits. Commit only when the phase checkpoint is green. (defined, 2026-10-14)
- [M-002] Branch `001-gmail-sync-table`; never commit to `main`; never push. (defined, 2026-10-14)
- [M-003] Extraction via local Ollama `qwen3:4b` over stdlib `urllib`; no `google-genai`, no `ollama` package (research R2). (defined, 2026-10-14)
- [M-004] Tests before implementation; run and confirm failing first (Constitution VIII). Tests never call Gmail or a live model. (defined, 2026-10-14)
