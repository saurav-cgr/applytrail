"""One sync run: search, filter, extract, merge, save (plan.md, data-model.md).

Plain code drives every step; the model only turns one email into one extraction
(Principle III). The caller's `Store` is mutated in place so a partial run can be saved.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal, Protocol

from applytrail import merge
from applytrail import store as store_file
from applytrail.config import FIRST_RUN_LOOKBACK_DAYS, OVERLAP, SAVE_EVERY, Settings
from applytrail.errors import AppError, ExtractionInvalid, GmailRateLimited, ProviderUnavailable
from applytrail.extractor import Extractor
from applytrail.models import (
    EmailMeta,
    MessageRef,
    ProcessedEmail,
    RunCounts,
    SearchPage,
    Store,
)

Progress = Callable[[int, int], None]
StopReason = Literal["complete", "provider_unavailable", "network", "interrupted"]


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
    extracting email `k` of `n`. On an `AppError` or Ctrl-C the stop is recorded in
    `store.sync` (checkpoint unchanged) and the error is re-raised for the CLI to save and
    report; a re-run resumes from `processed`.
    """
    progress = on_progress or (lambda k, n: None)
    counts = RunCounts()
    candidates: list[MessageRef] = []
    done = 0
    # Badges describe this run only, so they reset before anything (even the search) can fail.
    tracker = merge.BadgeTracker.begin(store)
    store.sync.added, store.sync.updated = [], []
    try:
        candidates = _candidates(store, mcp, now)
        total = len(candidates)
        progress(0, total)
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
                tracker.record(result)
                store.sync.added, store.sync.updated = tracker.badges(store)
            store.processed[email.message_id] = ProcessedEmail(
                message_id=email.message_id,
                date=email.date,
                outcome=outcome,
                reason=reason,
                application_key=key,
            )
            done = index
            newest = email.date if newest is None else max(newest, email.date)
            counts.read += 1
            if outcome == "ignored":
                counts.ignored += 1
            elif outcome == "skipped":
                counts.skipped += 1
            if index % SAVE_EVERY == 0:
                store_file.save(store, settings.store_path)
    except (AppError, KeyboardInterrupt) as error:
        pending = len(candidates) - done
        _finish(store, now, counts, _stop_reason(error), pending)
        raise _with_pending(error, pending) from None

    if newest is not None:
        checkpoint = store.sync.checkpoint
        store.sync.checkpoint = newest if checkpoint is None else max(checkpoint, newest)
    _finish(store, now, counts, "complete", 0)
    store_file.save(store, settings.store_path)
    return counts


def _finish(store: Store, now: datetime, counts: RunCounts, reason: StopReason, pending: int):
    counts.added = len(store.sync.added)
    counts.updated = len(store.sync.updated)
    store.sync.last_sync_at = now
    store.sync.last_sync_complete = reason == "complete"
    store.sync.stop_reason = reason
    store.sync.pending = pending
    store.sync.last_run_counts = counts


def _stop_reason(error: BaseException) -> StopReason:
    if isinstance(error, KeyboardInterrupt):
        return "interrupted"
    if isinstance(error, ProviderUnavailable):
        return "provider_unavailable"
    return "network"


def _with_pending(error: BaseException, pending: int) -> BaseException:
    """The same error, with the real number of pending emails in its message."""
    if isinstance(error, ProviderUnavailable):
        return ProviderUnavailable(error.reason, error.model, pending)
    if isinstance(error, GmailRateLimited):
        return GmailRateLimited(pending)
    return error


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
