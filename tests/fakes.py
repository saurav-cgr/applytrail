"""Test doubles for the MCP client and the extractor. They never touch Gmail or a model."""

import json
from datetime import datetime
from pathlib import Path

from applytrail.errors import AppError, ExtractionInvalid, ProviderUnavailable
from applytrail.models import EmailMeta, Extraction

FIXTURES = Path(__file__).parent / "fixtures"

EMAIL_FIELDS = ("message_id", "thread_id", "date", "sender", "subject", "body_text")


def load_fixture(name: str) -> dict:
    """Load one fixture by file name, with or without the `.json` suffix."""
    filename = name if name.endswith(".json") else f"{name}.json"
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


def load_fixtures(*names: str) -> list[dict]:
    """Load the named fixtures, or every fixture when no name is given."""
    if names:
        return [load_fixture(n) for n in names]
    return [load_fixture(p.name) for p in sorted(FIXTURES.glob("*.json"))]


def email_meta(fixture: dict) -> EmailMeta:
    return EmailMeta.model_validate({k: fixture[k] for k in EMAIL_FIELDS})


class FakeMcpClient:
    """Stands in for `mcp_client.GmailMcp`, backed by fixture dicts.

    `search_job_emails` returns the `structured_content` shape from contracts/mcp-tools.md,
    oldest first, `page_size` messages per page. `get_email` returns an `EmailMeta`.
    Every call is recorded in `calls`. With `fail_on_call=n`, the n-th call (1-based, across
    both methods) raises `error`.
    """

    def __init__(
        self,
        fixtures: list[dict],
        *,
        page_size: int = 500,
        fail_on_call: int | None = None,
        error: AppError | None = None,
    ) -> None:
        self.fixtures = {f["message_id"]: f for f in fixtures}
        self.page_size = page_size
        self.fail_on_call = fail_on_call
        self.error = error
        self.calls: list[tuple] = []

    def _record(self, call: tuple) -> None:
        self.calls.append(call)
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise self.error or AppError("fake failure")

    def search_job_emails(self, after: datetime, page_token: str | None = None) -> dict:
        self._record(("search_job_emails", after, page_token))
        matches = sorted(
            (email_meta(f) for f in self.fixtures.values()),
            key=lambda e: (e.date, e.message_id),
        )
        matches = [e for e in matches if e.date >= after]
        start = int(page_token or 0)
        page = matches[start : start + self.page_size]
        end = start + len(page)
        return {
            "messages": [
                {
                    "message_id": e.message_id,
                    "thread_id": e.thread_id,
                    "date": e.date.isoformat().replace("+00:00", "Z"),
                }
                for e in page
            ],
            "next_page_token": str(end) if end < len(matches) else None,
            "query": f"after:{int(after.timestamp())}",
        }

    def get_email(self, message_id: str) -> EmailMeta:
        self._record(("get_email", message_id))
        return email_meta(self.fixtures[message_id])

    @property
    def fetched_ids(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == "get_email"]


class FakeExtractor:
    """Stands in for `extractor.OllamaExtractor`, returning each fixture's `expected`.

    - `invalid_ids`: message IDs for which `extract` raises `ExtractionInvalid`.
    - `unavailable_on_call`: the n-th `extract` call (1-based) raises `ProviderUnavailable`.
    - `ready_error`: raised by `check_ready` when set.
    """

    def __init__(
        self,
        fixtures: list[dict],
        *,
        invalid_ids: set[str] | None = None,
        unavailable_on_call: int | None = None,
        ready_error: AppError | None = None,
        model: str = "fake-model",
    ) -> None:
        self.expected = {f["message_id"]: f["expected"] for f in fixtures}
        self.invalid_ids = invalid_ids or set()
        self.unavailable_on_call = unavailable_on_call
        self.ready_error = ready_error
        self.model = model
        self.ready_calls = 0
        self.calls = 0
        self.extracted_ids: list[str] = []

    def check_ready(self) -> None:
        self.ready_calls += 1
        if self.ready_error is not None:
            raise self.ready_error

    def extract(self, email: EmailMeta) -> Extraction:
        self.calls += 1
        self.extracted_ids.append(email.message_id)
        if self.unavailable_on_call is not None and self.calls == self.unavailable_on_call:
            raise ProviderUnavailable("unresponsive", self.model)
        if email.message_id in self.invalid_ids:
            raise ExtractionInvalid(f"invalid output for {email.message_id}")
        return Extraction.model_validate(self.expected[email.message_id])
