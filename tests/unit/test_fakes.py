"""Sanity checks for the fixtures and test doubles used by later phases."""

from datetime import UTC, datetime

import pytest

from applytrail.errors import AuthRequired, ExtractionInvalid, ProviderUnavailable
from applytrail.models import Extraction
from tests.fakes import FakeExtractor, FakeMcpClient, email_meta, load_fixtures

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def test_every_fixture_is_valid():
    fixtures = load_fixtures()
    assert len(fixtures) == 10
    for f in fixtures:
        email_meta(f)
        Extraction.model_validate(f["expected"])


def test_fixtures_never_mention_real_mail_domains():
    for f in load_fixtures():
        assert "@gmail.com" not in f["sender"]
        assert f["sender"].rstrip(">").endswith(".example")


def test_delayed_email_is_older_than_rejection():
    old, reject = load_fixtures("delayed_old_email", "reject_acme_backend")
    assert email_meta(old).date < email_meta(reject).date


def test_search_pages_oldest_first():
    mcp = FakeMcpClient(load_fixtures(), page_size=4)
    ids, token = [], None
    while True:
        page = mcp.search_job_emails(EPOCH, token)
        ids += [m["message_id"] for m in page["messages"]]
        token = page["next_page_token"]
        if token is None:
            break
    assert len(ids) == 10
    dates = [email_meta(f).date for f in load_fixtures()]
    assert len(mcp.calls) == 3
    assert sorted(dates) == [mcp.get_email(i).date for i in ids]


def test_search_filters_by_after():
    mcp = FakeMcpClient(load_fixtures())
    page = mcp.search_job_emails(datetime(2026, 10, 10, tzinfo=UTC))
    assert [m["message_id"] for m in page["messages"]] == ["msg-umbrella-001", "msg-acme-004"]


def test_mcp_raises_on_nth_call():
    mcp = FakeMcpClient(load_fixtures(), fail_on_call=2, error=AuthRequired())
    mcp.get_email("msg-acme-001")
    with pytest.raises(AuthRequired):
        mcp.get_email("msg-acme-002")
    assert mcp.fetched_ids == ["msg-acme-001", "msg-acme-002"]


def test_extractor_returns_expected_and_counts():
    fixtures = load_fixtures("confirm_acme_backend")
    ex = FakeExtractor(fixtures)
    result = ex.extract(email_meta(fixtures[0]))
    assert result.company == "Acme Inc."
    assert ex.calls == 1


def test_extractor_raises_on_demand():
    fixtures = load_fixtures("confirm_acme_backend", "newsletter")
    ex = FakeExtractor(fixtures, invalid_ids={"msg-news-001"}, unavailable_on_call=2)
    with pytest.raises(ExtractionInvalid):
        ex.extract(email_meta(fixtures[1]))
    with pytest.raises(ProviderUnavailable):
        ex.extract(email_meta(fixtures[0]))
