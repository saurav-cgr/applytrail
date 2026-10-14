"""Read-only Gmail MCP server over stdio (`applytrail-mcp`, contracts/mcp-tools.md).

Never writes to stdout outside the protocol, never opens a browser, never prompts.
"""

import logging
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field

from applytrail import gmail_auth, gmail_client
from applytrail.config import BODY_MAX_CHARS, Settings
from applytrail.errors import AuthRequired, GmailError, GmailRateLimited, NetworkUnavailable
from applytrail.models import EmailMeta, SearchPage

AUTH_REQUIRED_TEXT = "AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth."

server = MCPServer("applytrail-gmail")


@server.tool()
def search_job_emails(
    after: Annotated[datetime, Field(description="Lower bound (ISO 8601), inclusive")],
    max_results: Annotated[int, Field(ge=1, le=500, description="Per page")] = 500,
    page_token: Annotated[str | None, Field(description="From the previous call")] = None,
) -> Annotated[CallToolResult, SearchPage]:
    """List IDs of likely job-application emails received after a given time, oldest first.

    Returns one page. Pass `next_page_token` back as `page_token` for the next page. `query` is
    the Gmail search used, for transparency.
    """
    return _call(lambda: gmail_client.search(_service(), after, max_results, page_token))


@server.tool()
def get_email(
    message_id: str,
    max_chars: Annotated[int, Field(ge=500, le=20000, description="Body truncation")] = (
        BODY_MAX_CHARS
    ),
) -> Annotated[CallToolResult, EmailMeta]:
    """Fetch one email's headers and plain-text body, truncated for safe processing.

    Prefers the text/plain part; otherwise converts text/html to text. Whitespace is collapsed.
    `truncated` is true when the body was cut to `max_chars`.
    """
    return _call(lambda: gmail_client.get_email(_service(), message_id, max_chars))


def _service() -> Any:
    """Load (and refresh) the saved token on every call, so a new sign-in needs no restart."""
    return gmail_client.build_service(gmail_auth.load_credentials(Settings.from_env()))


def _call(produce: Callable[[], BaseModel]) -> CallToolResult:
    """Run one Gmail read. Expected failures become `is_error` results whose text starts with
    the prefix the CLI maps to an exit code. A `ToolError` would get the SDK's
    "Error executing tool ..." prefix, which the contract does not allow.
    """
    try:
        model = produce()
    except AuthRequired:
        return _error(AUTH_REQUIRED_TEXT)
    except NetworkUnavailable as err:
        return _error(f"NETWORK: {err.message}")
    except GmailRateLimited:
        return _error("RATE_LIMITED: Gmail rate limit reached.")
    except GmailError as err:
        return _error(f"GMAIL_ERROR: HTTP {err.status}")
    return CallToolResult(
        content=[TextContent(type="text", text=model.model_dump_json())],
        structured_content=model.model_dump(mode="json"),
    )


def _error(text: str) -> CallToolResult:
    logging.getLogger(__name__).info("tool failed: %s", text)
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=True)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    server.run("stdio")


if __name__ == "__main__":
    main()
