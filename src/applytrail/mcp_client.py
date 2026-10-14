"""The CLI side of the MCP protocol: spawn `applytrail-mcp` over stdio and wrap its two tools.

The rest of the CLI is synchronous, so the async `mcp.Client` runs in an anyio blocking portal
(an event loop on a helper thread) for the lifetime of the context manager.
"""

import os
import re
import sys
from contextlib import ExitStack
from datetime import datetime
from typing import Any, Self

from anyio.from_thread import BlockingPortal, start_blocking_portal
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult

from applytrail.config import Settings
from applytrail.errors import (
    AppError,
    AuthRequired,
    GmailError,
    GmailRateLimited,
    NetworkUnavailable,
)
from applytrail.models import EmailMeta, SearchPage

_GMAIL_STATUS = re.compile(r"^GMAIL_ERROR: HTTP (\d{3})\b")


class GmailMcp:
    """Context manager holding one MCP session. `server` (an in-process server) is for tests;
    by default the real server is spawned as a subprocess."""

    def __init__(self, settings: Settings, server: Any = None) -> None:
        self.settings = settings
        self._server = server
        self._stack: ExitStack | None = None
        self._portal: BlockingPortal | None = None
        self._client: Client | None = None

    def server_parameters(self) -> StdioServerParameters:
        # The full environment is passed on: PATH, proxy settings and certificates are needed
        # for Gmail. APPLYTRAIL_HOME is set explicitly so the server finds the same token.
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "applytrail.mcp_server"],
            env={**os.environ, "APPLYTRAIL_HOME": str(self.settings.home)},
        )

    def __enter__(self) -> Self:
        stack = ExitStack()
        try:
            portal = stack.enter_context(start_blocking_portal())
            target = self._server if self._server is not None else self.server_parameters()
            client = stack.enter_context(portal.wrap_async_context_manager(Client(target)))
        except BaseException:
            stack.close()
            raise
        self._stack, self._portal, self._client = stack, portal, client
        return self

    def __exit__(self, *exc_info: object) -> None:
        stack, self._stack, self._portal, self._client = self._stack, None, None, None
        if stack is not None:
            stack.close()

    def search_job_emails(self, after: datetime, page_token: str | None = None) -> SearchPage:
        arguments: dict[str, Any] = {"after": after.isoformat()}
        if page_token is not None:
            arguments["page_token"] = page_token
        result = self._call("search_job_emails", arguments)
        return SearchPage.model_validate(result.structured_content)

    def get_email(self, message_id: str) -> EmailMeta:
        result = self._call("get_email", {"message_id": message_id})
        return EmailMeta.model_validate(result.structured_content)

    def _call(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        if self._portal is None or self._client is None:
            raise RuntimeError("GmailMcp must be used as a context manager")
        result = self._portal.call(self._client.call_tool, name, arguments)
        if result.is_error:
            raise _error_from_text(_text(result))
        return result


def _text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content).strip()


def _error_from_text(text: str) -> AppError:
    """Map the server's prefixed error text (contracts/mcp-tools.md) back to a typed error."""
    if text.startswith("AUTH_REQUIRED:"):
        return AuthRequired()
    if text.startswith("NETWORK:"):
        return NetworkUnavailable()
    if text.startswith("RATE_LIMITED:"):
        return GmailRateLimited()
    match = _GMAIL_STATUS.match(text)
    # Anything else (including the SDK's generic text for a server-side crash) is a Gmail error.
    return GmailError(int(match.group(1)) if match else "unknown")
