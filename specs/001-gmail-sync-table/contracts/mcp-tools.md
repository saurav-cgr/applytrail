# Contract: MCP Server Tools

Server name: `applytrail-gmail`. Transport: stdio. Read-only (Principle I). The server never writes
to stdout outside the protocol and never opens a browser or prompts (Principle VI).

Auth: on each call the server loads `$APPLYTRAIL_HOME/token.json` and refreshes it if needed. If
the token is missing, invalid, or cannot be refreshed, the tool fails (`is_error = true`) with text
`AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth.`

Other Gmail failures return `is_error = true` with a prefix the CLI maps to exit codes:
`NETWORK:` (connection failures), `RATE_LIMITED:` (Gmail API HTTP 429 after server-side retry),
`GMAIL_ERROR:` (anything else, with the HTTP status).

## Tool: `search_job_emails`

> List IDs of likely job-application emails received after a given time, oldest first.

| Input | Type | Required | Notes |
|---|---|---|---|
| `after` | string (ISO 8601 datetime) | yes | Lower bound, inclusive |
| `max_results` | integer 1–500 | no, default 500 | Per page |
| `page_token` | string | no | From previous call |

Output (`structured_content`):

```json
{
  "messages": [{"message_id": "18c1…", "thread_id": "18c0…", "date": "2026-10-13T09:15:00Z"}],
  "next_page_token": null,
  "query": "after:1757000000 -in:chats …"
}
```

`messages` within a page are sorted by `date` ascending. The CLI collects all pages, then sorts
the full list newest first for processing (research R5). `query` is returned for transparency and debugging.

## Tool: `get_email`

> Fetch one email's headers and plain-text body, truncated for safe processing.

| Input | Type | Required | Notes |
|---|---|---|---|
| `message_id` | string | yes | |
| `max_chars` | integer 500–20000 | no, default 4000 | Body truncation (FR-022) |

Output (`structured_content`):

```json
{
  "message_id": "18c1…",
  "thread_id": "18c0…",
  "date": "2026-10-13T09:15:00Z",
  "sender": "Acme Recruiting <no-reply@greenhouse.io>",
  "subject": "Your application to Acme",
  "body_text": "Hi …",
  "truncated": true
}
```

Body extraction: prefer `text/plain` part; else `text/html` converted to text with the standard
library `html.parser` (tags dropped, scripts and styles removed); whitespace collapsed.

## Not provided (by design)

No send, draft, modify, label, trash, delete, or settings tools. Adding one requires a MAJOR
constitution amendment.
