"""Gmail API calls behind the MCP server: search and fetch only (FR-002, research R4).

Only `users().messages().list` and `users().messages().get` are ever called.
"""

import base64
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

import httplib2
from google.auth.exceptions import TransportError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from applytrail.config import BODY_MAX_CHARS
from applytrail.errors import GmailError, GmailRateLimited, NetworkUnavailable
from applytrail.models import EmailMeta, MessageRef, SearchPage

# Gmail search syntax: `{a b c}` matches any of the terms. Braces are doubled for str.format.
SEARCH_QUERY_TEMPLATE = (
    "after:{after} -in:chats -in:sent -in:drafts -category:promotions "
    "{{application applying applied interview candidate candidacy recruiter hiring assessment "
    '"your application" "thank you for applying" "next steps" "job offer" "offer letter" '
    "from:greenhouse.io from:lever.co from:myworkdayjobs.com from:workday.com "
    "from:ashbyhq.com from:smartrecruiters.com from:icims.com from:workablemail.com "
    "from:jobvite.com from:teamtailor.com}}"
)

# googleapiclient retries 429, 5xx and transient socket errors with backoff before raising.
NUM_RETRIES = 2

_BLOCK_TAGS = frozenset(
    "p div br li tr td th h1 h2 h3 h4 h5 h6 table ul ol blockquote hr section article "
    "header footer".split()
)
_SKIPPED_TAGS = frozenset({"script", "style"})


def build_query(after: datetime) -> str:
    return SEARCH_QUERY_TEMPLATE.format(after=int(after.timestamp()))


def build_service(creds: Any) -> Any:
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def search(
    service: Any, after: datetime, max_results: int = 500, page_token: str | None = None
) -> SearchPage:
    """Return one page of likely job emails received after `after`, oldest first."""
    query = build_query(after)
    messages = service.users().messages()
    with _mapped_errors():
        listing = messages.list(
            userId="me", q=query, maxResults=max_results, pageToken=page_token
        ).execute(num_retries=NUM_RETRIES)
        refs = []
        for item in listing.get("messages", []):
            meta = messages.get(
                userId="me", id=item["id"], format="metadata", metadataHeaders=["Date"]
            ).execute(num_retries=NUM_RETRIES)
            refs.append(
                MessageRef(
                    message_id=meta["id"], thread_id=meta["threadId"], date=_message_date(meta)
                )
            )
    refs.sort(key=lambda ref: ref.date)
    return SearchPage(messages=refs, next_page_token=listing.get("nextPageToken"), query=query)


def get_email(service: Any, message_id: str, max_chars: int = BODY_MAX_CHARS) -> EmailMeta:
    """Fetch headers and a plain-text body, whitespace collapsed and cut to `max_chars`."""
    with _mapped_errors():
        raw = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute(num_retries=NUM_RETRIES)
        )
    payload = raw.get("payload", {})
    text = " ".join(_body_text(payload).split())
    truncated = len(text) > max_chars
    return EmailMeta(
        message_id=raw["id"],
        thread_id=raw["threadId"],
        date=_message_date(raw),
        sender=_header(payload, "From"),
        subject=_header(payload, "Subject"),
        body_text=text[:max_chars],
        truncated=truncated,
    )


@contextmanager
def _mapped_errors() -> Iterator[None]:
    try:
        yield
    except HttpError as err:
        status = err.resp.status
        if status == 429:
            raise GmailRateLimited() from err
        raise GmailError(status) from err
    except (OSError, httplib2.HttpLib2Error, TransportError) as err:
        raise NetworkUnavailable() from err


def _header(payload: dict, name: str) -> str:
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _message_date(raw: dict) -> datetime:
    """The `Date` header in UTC; Gmail's `internalDate` if the header is missing or unusable."""
    value = _header(raw.get("payload", {}), "Date")
    try:
        parsed = parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        parsed = None
    if parsed is not None and parsed.tzinfo is not None:
        return parsed.astimezone(UTC)
    return datetime.fromtimestamp(int(raw["internalDate"]) / 1000, tz=UTC)


def _body_text(payload: dict) -> str:
    plain = _first_part(payload, "text/plain")
    if plain is not None:
        return plain
    html = _first_part(payload, "text/html")
    return _html_to_text(html) if html is not None else ""


def _first_part(part: dict, mime_type: str) -> str | None:
    """Depth-first search for the first inline part of `mime_type` with body data."""
    data = part.get("body", {}).get("data")
    if part.get("mimeType") == mime_type and data and not part.get("filename"):
        return _decode(data)
    for child in part.get("parts", []):
        found = _first_part(child, mime_type)
        if found is not None:
            return found
    return None


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.chunks.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return "".join(parser.chunks)
