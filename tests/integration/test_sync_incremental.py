"""Later sync runs against fakes: overlap, badges, resume after a stop (T035, spec US2)."""

from datetime import UTC, datetime, timedelta

import pytest

from applytrail import render, store, sync
from applytrail.config import OVERLAP, Settings
from applytrail.errors import (
    AuthRequired,
    GmailRateLimited,
    NetworkUnavailable,
    ProviderUnavailable,
)
from applytrail.models import Store
from tests.fakes import FakeExtractor, FakeMcpClient, load_fixture

FIRST_RUN = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
SECOND_RUN = FIRST_RUN + timedelta(days=1)
ACME = "acme|backend engineer"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
    return Settings.from_env()


def fixture(name, **overrides):
    return {**load_fixture(name), **overrides}


def companies(n: int, start: datetime) -> list[dict]:
    """`n` application confirmations for different companies, one hour apart, newest first."""
    base = load_fixture("confirm_acme_backend")
    return [
        {
            **base,
            "message_id": f"msg-co-{i:03d}",
            "thread_id": f"thr-co-{i:03d}",
            "date": (start - timedelta(hours=i)).isoformat(),
            "expected": {**base["expected"], "company": f"Company {i:03d}"},
        }
        for i in range(n)
    ]


def sync_once(data, fixtures, settings, now, **extractor_options):
    mcp = FakeMcpClient(fixtures)
    extractor = FakeExtractor(fixtures, **extractor_options)
    sync.run_sync(data, mcp, extractor, settings, now)
    return mcp, extractor


def first_store(settings) -> Store:
    data = Store.empty()
    sync_once(data, [fixture("confirm_acme_backend")], settings, FIRST_RUN)
    return data


def applications_json(data: Store) -> str:
    return data.model_dump_json(include={"applications"})


# --- Overlap and skipping ----------------------------------------------------------------------


def test_second_run_searches_from_checkpoint_minus_overlap(settings):
    data = first_store(settings)
    checkpoint = data.sync.checkpoint

    mcp, _ = sync_once(data, [fixture("confirm_acme_backend")], settings, SECOND_RUN)

    assert mcp.calls[0] == ("search_job_emails", checkpoint - OVERLAP, None)
    assert OVERLAP == timedelta(hours=1)


def test_overlap_messages_already_processed_are_not_fetched_or_extracted(settings):
    data = first_store(settings)
    # The first email sits inside the overlap window again; the new one is after it.
    new = fixture("reject_acme_backend")
    fixtures = [fixture("confirm_acme_backend", date=data.sync.checkpoint.isoformat()), new]

    mcp, extractor = sync_once(data, fixtures, settings, SECOND_RUN)

    assert mcp.fetched_ids == [new["message_id"]]
    assert extractor.extracted_ids == [new["message_id"]]


# --- Badges --------------------------------------------------------------------------------------


def test_new_application_is_added_and_status_change_is_updated(settings):
    data = first_store(settings)
    assert data.sync.added == [ACME]

    globex = fixture("interview_globex_data")
    sync_once(data, [fixture("reject_acme_backend"), globex], settings, SECOND_RUN)

    globex_key = data.processed[globex["message_id"]].application_key
    assert data.sync.added == [globex_key]
    assert data.sync.updated == [ACME]


def test_status_change_moves_the_row_to_the_top(settings):
    data = Store.empty()
    fixtures = [fixture("confirm_acme_backend"), fixture("interview_globex_data")]
    sync_once(data, fixtures, settings, FIRST_RUN)
    assert sorted(data.applications.values(), key=render.sort_key)[0].key != ACME

    sync_once(data, [fixture("reject_acme_backend")], settings, SECOND_RUN)

    assert sorted(data.applications.values(), key=render.sort_key)[0].key == ACME
    assert data.sync.updated == [ACME]


def test_no_new_mail_changes_nothing(settings):
    data = first_store(settings)
    sync_once(data, [fixture("reject_acme_backend")], settings, SECOND_RUN)
    applications = applications_json(data)
    checkpoint = data.sync.checkpoint

    sync_once(data, [fixture("reject_acme_backend")], settings, SECOND_RUN + timedelta(days=1))

    assert data.sync.added == []
    assert data.sync.updated == []
    assert data.sync.checkpoint == checkpoint
    assert applications_json(data) == applications
    saved = store.load(settings.store_path)
    assert saved.sync.added == saved.sync.updated == []


# --- Stopping and resuming -------------------------------------------------------------------


def test_ollama_failure_saves_partial_state_and_resume_finishes(settings):
    data = first_store(settings)
    checkpoint = data.sync.checkpoint
    fixtures = companies(20, SECOND_RUN - timedelta(hours=1))

    with pytest.raises(ProviderUnavailable) as stopped:
        sync_once(data, fixtures, settings, SECOND_RUN, unavailable_on_call=13)

    new_ids = {f["message_id"] for f in fixtures}
    assert len(new_ids & data.processed.keys()) == 12
    assert data.sync.checkpoint == checkpoint
    assert data.sync.stop_reason == "provider_unavailable"
    assert data.sync.pending == 8
    assert data.sync.last_sync_complete is False
    assert len(data.sync.added) == 12
    assert stopped.value.pending == 8
    assert "8 emails pending" in stopped.value.message

    _, extractor = sync_once(data, fixtures, settings, SECOND_RUN + timedelta(minutes=5))

    assert sorted(extractor.extracted_ids) == [f"msg-co-{i:03d}" for i in range(12, 20)]
    assert new_ids <= data.processed.keys()
    assert data.sync.stop_reason == "complete"
    assert data.sync.pending == 0
    assert data.sync.last_sync_complete is True
    assert data.sync.checkpoint > checkpoint


def test_ctrl_c_saves_interrupted_state_and_resume_finishes(settings):
    data = first_store(settings)
    checkpoint = data.sync.checkpoint
    fixtures = companies(20, SECOND_RUN - timedelta(hours=1))

    with pytest.raises(KeyboardInterrupt):
        sync_once(data, fixtures, settings, SECOND_RUN, interrupt_on_call=13)

    assert data.sync.stop_reason == "interrupted"
    assert data.sync.pending == 8
    assert data.sync.last_sync_complete is False
    assert data.sync.checkpoint == checkpoint

    _, extractor = sync_once(data, fixtures, settings, SECOND_RUN + timedelta(minutes=5))

    assert len(extractor.extracted_ids) == 8
    assert data.sync.stop_reason == "complete"


def test_gmail_rate_limit_mid_run_reports_pending(settings):
    data = first_store(settings)
    fixtures = companies(5, SECOND_RUN - timedelta(hours=1))
    # Calls: 1 search, then get_email per candidate; the 4th call is the 3rd get_email.
    mcp = FakeMcpClient(fixtures, fail_on_call=4, error=GmailRateLimited())

    with pytest.raises(GmailRateLimited) as stopped:
        sync.run_sync(data, mcp, FakeExtractor(fixtures), settings, SECOND_RUN)

    assert data.sync.pending == 3
    assert data.sync.stop_reason == "network"
    assert stopped.value.pending == 3
    assert "3 emails pending" in stopped.value.message


@pytest.mark.parametrize(
    "error",
    [NetworkUnavailable(), GmailRateLimited(), KeyboardInterrupt()],
    ids=["network", "rate-limit", "ctrl-c"],
)
def test_stop_during_search_clears_badges_and_keeps_data(settings, error):
    # Badges describe the latest run, which reset them at its start (data-model.md SyncState).
    data = first_store(settings)
    assert data.sync.added == [ACME]
    before = data.model_copy(deep=True)
    mcp = FakeMcpClient([], fail_on_call=1, error=error)

    with pytest.raises(type(error)):
        sync.run_sync(data, mcp, FakeExtractor([]), settings, SECOND_RUN)

    assert data.sync.added == data.sync.updated == []
    assert data.sync.last_run_counts.added == data.sync.last_run_counts.updated == 0
    assert data.sync.last_run_counts.read == 0
    assert data.sync.last_sync_complete is False
    assert data.sync.pending == 0
    assert data.sync.checkpoint == before.sync.checkpoint
    assert applications_json(data) == applications_json(before)
    assert data.processed == before.processed


# --- Synced mailbox (002 US3, T036) -----------------------------------------------------------


def saved_without_last_sync_at(settings) -> dict:
    import json

    saved = json.loads(settings.store_path.read_text(encoding="utf-8"))
    del saved["sync"]["last_sync_at"]
    return saved


def test_rerun_with_same_account_and_no_new_mail_changes_only_last_sync_at(settings):
    data = first_store(settings)
    later = SECOND_RUN + timedelta(days=1)
    sync_once(data, [fixture("confirm_acme_backend")], settings, SECOND_RUN)
    before = saved_without_last_sync_at(settings)

    mcp, _ = sync_once(data, [fixture("confirm_acme_backend")], settings, later)

    assert mcp.account_calls == [0]
    assert saved_without_last_sync_at(settings) == before
    assert before["sync"]["mailbox"] == "me@example.com"
    assert store.load(settings.store_path).sync.last_sync_at == later


def test_different_account_replaces_the_mailbox(settings):
    data = first_store(settings)
    mcp = FakeMcpClient([fixture("confirm_acme_backend")], account="other@example.com")
    sync.run_sync(data, mcp, FakeExtractor([]), settings, SECOND_RUN)

    assert data.sync.mailbox == "other@example.com"
    assert store.load(settings.store_path).sync.mailbox == "other@example.com"


def test_get_account_failure_stops_the_run_and_keeps_the_mailbox(settings):
    data = first_store(settings)
    before = data.model_copy(deep=True)
    mcp = FakeMcpClient([fixture("reject_acme_backend")], account_error=AuthRequired())

    with pytest.raises(AuthRequired):
        sync.run_sync(data, mcp, FakeExtractor([]), settings, SECOND_RUN)

    assert mcp.calls == []  # stopped before searching
    assert data.sync.mailbox == "me@example.com"
    assert data.sync.last_sync_complete is False
    assert data.sync.checkpoint == before.sync.checkpoint
    assert data.sync.added == data.sync.updated == []
    assert applications_json(data) == applications_json(before)
    assert data.processed == before.processed
