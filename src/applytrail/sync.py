"""One sync run: search, filter, extract, merge, save (plan.md, data-model.md).

Plain code drives every step; the model only turns one email into one extraction
(Principle III). The caller's `Store` is mutated in place so a partial run can be saved.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from applytrail import merge
from applytrail import store as store_file
from applytrail.config import FIRST_RUN_LOOKBACK_DAYS, OVERLAP, SAVE_EVERY, Settings
from applytrail.errors import ExtractionInvalid
from applytrail.extractor import Extractor
from applytrail.models import (
    Application,
    EmailMeta,
    MessageRef,
    ProcessedEmail,
    RunCounts,
    SearchPage,
    Store,
)

Progress = Callable[[int, int], None]


class MailSource(Protocol):
    def search_job_emails(self, after: datetime, page_token: str | None = None) -> SearchPage: ...

    def get_email(self, message_id: str) -> EmailMeta: ...


def run_sync(
    store: Store,
    mcp: MailSource,
    extractor: Extractor,
    settings: Settings,
    now: datetime,
    on_progress: Progress | None = None,
) -> RunCounts:
    """Process every new candidate email newest first and return the run's counts.

    `on_progress(k, n)` is called with `k = 0` once the candidate list is known, then before
    extracting email `k` of `n`.
    """
    progress = on_progress or (lambda k, n: None)
    candidates = _candidates(store, mcp, now)
    total = len(candidates)
    progress(0, total)

    snapshot = {k: _badge_fields(a) for k, a in store.applications.items()}
    created: set[str] = set()
    counts = RunCounts()
    newest: datetime | None = None

    for index, ref in enumerate(candidates, start=1):
        progress(index, total)
        email = mcp.get_email(ref.message_id)
        try:
            extraction = extractor.extract(email)
        except ExtractionInvalid as err:
            extraction = err
        outcome, reason = merge.classify(extraction)
        key = None
        if outcome == "applied":
            result = merge.apply(store, extraction, email)
            key = result.key
            if result.rekeyed_from is not None:
                if result.rekeyed_from in snapshot:
                    snapshot[key] = snapshot.pop(result.rekeyed_from)
                if result.rekeyed_from in created:
                    created.discard(result.rekeyed_from)
                    created.add(key)
            if result.created:
                created.add(key)
        store.processed[email.message_id] = ProcessedEmail(
            message_id=email.message_id,
            date=email.date,
            outcome=outcome,
            reason=reason,
            application_key=key,
        )
        newest = email.date if newest is None else max(newest, email.date)
        counts.read += 1
        if outcome == "ignored":
            counts.ignored += 1
        elif outcome == "skipped":
            counts.skipped += 1
        if index % SAVE_EVERY == 0:
            store_file.save(store, settings.store_path)

    counts.added = len(created)
    counts.updated = sum(
        1
        for key, fields in snapshot.items()
        if key in store.applications and _badge_fields(store.applications[key]) != fields
    )
    if newest is not None:
        checkpoint = store.sync.checkpoint
        store.sync.checkpoint = newest if checkpoint is None else max(checkpoint, newest)
    store.sync.last_sync_at = now
    store.sync.last_sync_complete = True
    store.sync.stop_reason = "complete"
    store.sync.pending = 0
    store.sync.last_run_counts = counts
    store_file.save(store, settings.store_path)
    return counts


def _candidates(store: Store, mcp: MailSource, now: datetime) -> list[MessageRef]:
    """All search hits not yet processed, newest first."""
    checkpoint = store.sync.checkpoint
    if checkpoint is None:
        after = now - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)
    else:
        after = checkpoint - OVERLAP
    refs: dict[str, MessageRef] = {}
    page_token = None
    while True:
        page = mcp.search_job_emails(after, page_token)
        for ref in page.messages:
            if ref.message_id not in store.processed:
                refs[ref.message_id] = ref
        page_token = page.next_page_token
        if page_token is None:
            break
    return sorted(refs.values(), key=lambda r: (r.date, r.message_id), reverse=True)


def _badge_fields(app: Application) -> tuple:
    return (app.status, app.role, app.last_activity)
