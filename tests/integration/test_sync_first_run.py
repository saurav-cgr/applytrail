"""First sync run against fakes: no Gmail, no model (T028)."""

from datetime import UTC, datetime, timedelta

import pytest

from applytrail import store, sync
from applytrail.config import FIRST_RUN_LOOKBACK_DAYS, Settings
from applytrail.models import RunCounts, Store
from applytrail.normalize import make_key, norm_company, norm_role
from tests.fakes import FakeExtractor, FakeMcpClient, load_fixture, load_fixtures

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
    return Settings.from_env()


@pytest.fixture
def saves(monkeypatch):
    """Spy on `store.save`; each entry is a snapshot of the store as written."""
    calls: list[Store] = []
    real_save = store.save

    def spy(data: Store, path):
        calls.append(data.model_copy(deep=True))
        real_save(data, path)

    monkeypatch.setattr(store, "save", spy)
    return calls


def run(fixtures, settings, *, page_size=500, invalid_ids=None, progress=None):
    data = Store.empty()
    mcp = FakeMcpClient(fixtures, page_size=page_size)
    extractor = FakeExtractor(fixtures, invalid_ids=invalid_ids)
    counts = sync.run_sync(
        data,
        mcp,
        extractor,
        settings,
        NOW,
        on_progress=(None if progress is None else lambda k, n: progress.append((k, n))),
    )
    return data, mcp, extractor, counts


def key_for(company, role):
    return make_key(norm_company(company), norm_role(role))


def newsletters(n: int) -> list[dict]:
    """`n` non-job emails, one hour apart, newest on 2026-10-13."""
    base = load_fixture("newsletter")
    start = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
    return [
        {
            **base,
            "message_id": f"msg-news-{i:03d}",
            "thread_id": f"thr-news-{i:03d}",
            "date": (start - timedelta(hours=i)).isoformat(),
        }
        for i in range(n)
    ]


def test_empty_store_searches_the_first_run_window(settings):
    _, mcp, _, _ = run(load_fixtures(), settings)

    after = mcp.calls[0][1]
    assert mcp.calls[0][0] == "search_job_emails"
    assert after == NOW - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)


def test_collects_all_pages_and_processes_newest_first(settings):
    fixtures = load_fixtures()
    _, mcp, extractor, _ = run(fixtures, settings, page_size=3)

    searches = [c for c in mcp.calls if c[0] == "search_job_emails"]
    assert [c[2] for c in searches] == [None, "3", "6", "9"]
    # Every page is collected before the first email is fetched.
    assert [c[0] for c in mcp.calls[:4]] == ["search_job_emails"] * 4
    newest_first = [
        f["message_id"] for f in sorted(fixtures, key=lambda f: f["date"], reverse=True)
    ]
    assert mcp.fetched_ids == newest_first
    assert extractor.extracted_ids == newest_first


def test_each_message_fetched_extracted_and_recorded_once(settings):
    fixtures = load_fixtures()
    data, mcp, extractor, _ = run(fixtures, settings, page_size=4)

    ids = {f["message_id"] for f in fixtures}
    assert sorted(mcp.fetched_ids) == sorted(ids)
    assert sorted(extractor.extracted_ids) == sorted(ids)
    assert set(data.processed) == ids


def test_processed_records_outcome_reason_and_key(settings):
    fixtures = load_fixtures()
    data, *_ = run(fixtures, settings, invalid_ids={"msg-umbrella-001"})

    acme = data.processed["msg-acme-001"]
    assert acme.outcome == "applied"
    assert acme.reason is None
    assert acme.application_key == key_for("Acme", "Backend Engineer")
    assert acme.date == datetime(2026, 9, 30, 8, 11, tzinfo=UTC)

    news = data.processed["msg-news-001"]
    assert (news.outcome, news.reason, news.application_key) == ("ignored", None, None)

    invalid = data.processed["msg-umbrella-001"]
    assert (invalid.outcome, invalid.reason) == ("skipped", "invalid_output")
    assert invalid.application_key is None


def test_saves_every_ten_emails_and_at_the_end(settings, saves):
    data, *_ = run(newsletters(25), settings)

    assert [len(s.processed) for s in saves] == [10, 20, 25]
    assert saves[-1] == data
    assert store.load(settings.store_path) == data


def test_ten_emails_save_at_ten_and_again_at_the_end(settings, saves):
    run(load_fixtures(), settings)

    assert [len(s.processed) for s in saves] == [10, 10]
    assert saves[0].sync.last_sync_complete is False
    assert saves[-1].sync.last_sync_complete is True


def test_completion_sets_checkpoint_and_sync_state(settings):
    data, _, _, counts = run(load_fixtures(), settings)

    assert data.sync.checkpoint == datetime(2026, 10, 12, 14, 3, tzinfo=UTC)
    assert data.sync.last_sync_at == NOW
    assert data.sync.last_sync_complete is True
    assert data.sync.stop_reason == "complete"
    assert data.sync.pending == 0
    expected = RunCounts(read=10, added=4, updated=0, ignored=3, skipped=0)
    assert counts == expected
    assert data.sync.last_run_counts == expected


def test_first_run_builds_the_expected_applications(settings):
    data, *_ = run(load_fixtures(), settings)

    acme = data.applications[key_for("Acme", "Backend Engineer")]
    assert acme.status == "rejected"
    assert acme.first_seen == datetime(2026, 9, 30, 8, 11, tzinfo=UTC)
    assert acme.last_activity == datetime(2026, 10, 12, 14, 3, tzinfo=UTC)
    assert sorted(acme.message_ids) == [
        "msg-acme-001",
        "msg-acme-002",
        "msg-acme-003",
        "msg-acme-004",
    ]
    assert set(data.applications) == {
        key_for("Acme", "Backend Engineer"),
        key_for("Umbrella Labs", "Product Designer"),
        key_for("Globex", "Data Engineer"),
        key_for("Initech", None),
    }


def test_newsletter_and_alert_are_ignored_and_create_nothing(settings):
    fixtures = load_fixtures("newsletter", "job_alert")
    data, _, _, counts = run(fixtures, settings)

    assert data.applications == {}
    assert {p.outcome for p in data.processed.values()} == {"ignored"}
    assert counts == RunCounts(read=2, ignored=2)


def test_injection_fixture_yields_at_most_one_row(settings):
    data, *_ = run(load_fixtures("injection_attempt"), settings)

    assert len(data.applications) <= 1


def test_skipped_counts_invalid_and_incomplete(settings):
    incomplete = {
        **load_fixture("interview_globex_data"),
        "message_id": "msg-globex-002",
        "expected": {
            "is_job_application": True,
            "company": "Globex",
            "role": None,
            "status": "unknown",
            "evidence": "",
        },
    }
    fixtures = [load_fixture("html_only_body"), incomplete]
    data, _, _, counts = run(fixtures, settings, invalid_ids={"msg-umbrella-001"})

    assert data.applications == {}
    assert data.processed["msg-globex-002"].reason == "incomplete"
    assert counts == RunCounts(read=2, skipped=2)


def test_empty_mailbox_gives_nothing(settings):
    data, mcp, extractor, counts = run([], settings)

    assert data.applications == {}
    assert data.processed == {}
    assert counts == RunCounts()
    assert mcp.fetched_ids == []
    assert extractor.calls == 0
    assert data.sync.checkpoint is None
    assert data.sync.last_sync_complete is True
    assert data.sync.stop_reason == "complete"
    assert data.sync.pending == 0


def test_progress_reports_position_and_total(settings):
    progress = []
    run(load_fixtures("newsletter", "job_alert", "html_only_body"), settings, progress=progress)

    assert progress == [(0, 3), (1, 3), (2, 3), (3, 3)]


# --- Synced mailbox (002 US3, T036) -----------------------------------------------------------


def test_first_sync_saves_the_mailbox(settings):
    data, mcp, _, _ = run(load_fixtures(), settings)

    assert data.sync.mailbox == "me@example.com"
    assert store.load(settings.store_path).sync.mailbox == "me@example.com"
    # Exactly once per run, before the first search.
    assert mcp.account_calls == [0]
