"""Read-only Gmail MCP server over stdio (`applytrail-mcp`, contracts/mcp-tools.md).

Never writes to stdout outside the protocol, never opens a browser, never prompts.
"""

import logging
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from applytrail import gmail_auth, gmail_client
from applytrail.config import BODY_MAX_CHARS, Settings
from applytrail.errors import AuthRequired, GmailError, GmailRateLimited, NetworkUnavailable
from applytrail.models import AccountInfo, EmailMeta, SearchPage

M = TypeVar("M", bound=BaseModel)

AUTH_REQUIRED_TEXT = "AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth."

# Unexpected exceptions reach the client as "Error calling tool '<name>'", without details.
server = FastMCP("applytrail-gmail", mask_error_details=True)


@server.tool
def search_job_emails(
    after: Annotated[datetime, Field(description="Lower bound (ISO 8601), inclusive")],
    max_results: Annotated[int, Field(ge=1, le=500, description="Per page")] = 500,
    page_token: Annotated[str | None, Field(description="From the previous call")] = None,
) -> SearchPage:
    """List IDs of likely job-application emails received after a given time, oldest first.

    Returns one page. Pass `next_page_token` back as `page_token` for the next page. `query` is
    the Gmail search used, for transparency.
    """
    return _call(lambda: gmail_client.search(_service(), after, max_results, page_token))


@server.tool
def get_email(
    message_id: str,
    max_chars: Annotated[int, Field(ge=500, le=20000, description="Body truncation")] = (
        BODY_MAX_CHARS
    ),
) -> EmailMeta:
    """Fetch one email's headers and plain-text body, truncated for safe processing.

    Prefers the text/plain part; otherwise converts text/html to text. Whitespace is collapsed.
    `truncated` is true when the body was cut to `max_chars`.
    """
    return _call(lambda: gmail_client.get_email(_service(), message_id, max_chars))


@server.tool
def get_account() -> AccountInfo:
    """Return the address of the Gmail account this server reads, so links can open the right mailbox."""  # noqa: E501
    # The address is never logged (data-model.md SyncState.mailbox).
    return _call(lambda: gmail_client.get_account(_service()))


def _service() -> Any:
    """Load (and refresh) the saved token on every call, so a new sign-in needs no restart."""
    return gmail_client.build_service(gmail_auth.load_credentials(Settings.from_env()))


def _call(produce: Callable[[], M]) -> M:
    """Run one Gmail read. Expected failures become `ToolError`s whose text starts with the prefix
    the CLI maps to an exit code; FastMCP sends that text to the client verbatim.
    """
    try:
        return produce()
    except AuthRequired:
        raise _error(AUTH_REQUIRED_TEXT) from None
    except NetworkUnavailable as err:
        raise _error(f"NETWORK: {err.message}") from None
    except GmailRateLimited:
        raise _error("RATE_LIMITED: Gmail rate limit reached.") from None
    except GmailError as err:
        raise _error(f"GMAIL_ERROR: HTTP {err.status}") from None


def _error(text: str) -> ToolError:
    logging.getLogger(__name__).info("tool failed: %s", text)
    return ToolError(text)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    server.run("stdio", show_banner=False)


if __name__ == "__main__":
    main()
