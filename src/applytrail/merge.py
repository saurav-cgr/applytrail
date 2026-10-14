"""Deterministic merge of one extraction into the store (data-model.md "Merge rules").

Pure functions on the in-memory `Store`; no I/O and no model calls (Principle III).
"""

from dataclasses import dataclass
from typing import Literal

from applytrail.models import Application, EmailMeta, Extraction, Store
from applytrail.normalize import make_key, norm_company, norm_role

Outcome = Literal["applied", "ignored", "skipped"]
Reason = Literal["invalid_output", "incomplete"]

MAX_TEXT = 200


@dataclass(frozen=True)
class MergeResult:
    key: str
    created: bool
    rekeyed_from: str | None = None


def classify(extraction: Extraction | BaseException | None) -> tuple[Outcome, Reason | None]:
    """Outcome for one email. `None` or an exception means the model output failed validation."""
    if not isinstance(extraction, Extraction):
        return "skipped", "invalid_output"
    if not extraction.is_job_application:
        return "ignored", None
    if not extraction.company.strip() or extraction.status == "unknown":
        return "skipped", "incomplete"
    return "applied", None


def apply(store: Store, extraction: Extraction, email: EmailMeta) -> MergeResult:
    """Apply a usable extraction (classify == applied) to the store, following rules 1-3."""
    if classify(extraction) != ("applied", None):
        raise ValueError("only a usable extraction can be applied")
    ck = norm_company(extraction.company)
    rk = norm_role(extraction.role)
    company_keys = [k for k in store.applications if k.partition("|")[0] == ck]
    unknown_key = make_key(ck, "")

    rekeyed_from = None
    if rk:
        key = make_key(ck, rk)
        if key not in store.applications and company_keys == [unknown_key]:
            _rekey(store, unknown_key, key, extraction.role)
            rekeyed_from = unknown_key
    elif len(company_keys) == 1:
        key = company_keys[0]
    else:
        key = unknown_key

    app = store.applications.get(key)
    if app is None:
        store.applications[key] = Application(
            key=key,
            company=extraction.company,
            role=extraction.role,
            status=extraction.status,
            last_activity=email.date,
            first_seen=email.date,
            thread_id=email.thread_id,
            subject=email.subject[:MAX_TEXT],
            evidence=extraction.evidence[:MAX_TEXT],
            message_ids=[email.message_id],
        )
        return MergeResult(key=key, created=True)

    if email.message_id not in app.message_ids:
        app.message_ids.append(email.message_id)
    app.first_seen = min(app.first_seen, email.date)
    if email.date >= app.last_activity:
        app.status = extraction.status
        app.last_activity = email.date
        app.thread_id = email.thread_id
        app.subject = email.subject[:MAX_TEXT]
        app.evidence = extraction.evidence[:MAX_TEXT]
        app.company = extraction.company
        if app.role is None:
            app.role = extraction.role
    return MergeResult(key=key, created=False, rekeyed_from=rekeyed_from)


def _rekey(store: Store, old: str, new: str, role: str | None) -> None:
    """Move `ck|` to `ck|rk`, filling in the role, and point processed emails at the new key."""
    app = store.applications.pop(old)
    app.key = new
    app.role = role
    store.applications[new] = app
    for processed in store.processed.values():
        if processed.application_key == old:
            processed.application_key = new
