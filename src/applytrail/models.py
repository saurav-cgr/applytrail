"""Pydantic models for extraction input/output and the local store (data-model.md)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]

_LABELS = {
    "applied": "Applied",
    "in_review": "In Review",
    "assessment": "Assessment",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}


class Status(StrEnum):
    APPLIED = "applied"
    IN_REVIEW = "in_review"
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

    @property
    def label(self) -> str:
        return _LABELS[self.value]


class Extraction(BaseModel):
    """One model answer for one email. Validated, never repaired."""

    is_job_application: bool
    company: str
    role: str | None
    status: Status | Literal["unknown"]
    evidence: str = Field(max_length=200)

    @field_validator("company", mode="before")
    @classmethod
    def _trim_company(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("role", mode="before")
    @classmethod
    def _trim_role(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class EmailMeta(BaseModel):
    """One email as returned by the MCP `get_email` tool. Never stored."""

    message_id: str
    thread_id: str
    date: UtcDatetime
    sender: str
    subject: str
    body_text: str
    truncated: bool = False


class MessageRef(BaseModel):
    """One search hit from the MCP `search_job_emails` tool."""

    message_id: str
    thread_id: str
    date: UtcDatetime


class SearchPage(BaseModel):
    """One page of `search_job_emails` results, oldest first (contracts/mcp-tools.md)."""

    messages: list[MessageRef]
    next_page_token: str | None = None
    query: str


class Application(BaseModel):
    key: str
    company: str
    role: str | None
    status: Status
    last_activity: UtcDatetime
    first_seen: UtcDatetime
    thread_id: str
    subject: str = Field(max_length=200)
    evidence: str = Field(max_length=200)
    message_ids: list[str]


class ProcessedEmail(BaseModel):
    message_id: str
    date: UtcDatetime
    outcome: Literal["applied", "ignored", "skipped"]
    reason: Literal["invalid_output", "incomplete"] | None = None
    application_key: str | None = None


class RunCounts(BaseModel):
    read: int = 0
    added: int = 0
    updated: int = 0
    ignored: int = 0
    skipped: int = 0


class SyncState(BaseModel):
    checkpoint: UtcDatetime | None = None
    last_sync_at: UtcDatetime | None = None
    last_sync_complete: bool = False
    stop_reason: Literal["complete", "provider_unavailable", "network", "interrupted"] | None = None
    pending: int = 0
    added: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    last_run_counts: RunCounts = Field(default_factory=RunCounts)

    @model_validator(mode="after")
    def _complete_has_nothing_pending(self) -> "SyncState":
        complete = self.last_sync_complete or self.stop_reason == "complete"
        if complete and self.pending != 0:
            raise ValueError("pending must be 0 when the last sync is complete")
        return self


class Store(BaseModel):
    schema_version: Literal[1]
    applications: dict[str, Application]
    processed: dict[str, ProcessedEmail]
    sync: SyncState

    @field_validator("schema_version", mode="before")
    @classmethod
    def _version_is_an_integer(cls, value: object) -> object:
        # Literal[1] alone would accept JSON `true` and `1.0` as version 1.
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @classmethod
    def empty(cls) -> "Store":
        return cls(schema_version=1, applications={}, processed={}, sync=SyncState())
