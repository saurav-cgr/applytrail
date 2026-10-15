# Contract: MCP Server Tools (changes)

Extends [001 contracts/mcp-tools.md](../../001-gmail-sync-table/contracts/mcp-tools.md). Server
name, transport, auth handling, error prefixes, and the existing `search_job_emails` and
`get_email` tools are unchanged.

## New tool: `get_account`

> Return the address of the Gmail account this server reads, so links can open the right mailbox.

No inputs.

Output (`structured_content`):

```json
{"email_address": "me+jobs@example.com"}
```

- Gmail call: `users().getProfile(userId="me")`, read-only and covered by `gmail.readonly`.
- Errors: same as the other tools (`AUTH_REQUIRED:`, `NETWORK:`, `RATE_LIMITED:`,
  `GMAIL_ERROR:`).
- The server never logs the address.

The CLI calls it once at the start of each sync (research R7).

## Not provided (by design)

Unchanged: no send, draft, modify, label, trash, delete, or settings tools.
