"""Row numbers for lookup and open (T004, research R5)."""

from datetime import UTC, datetime

import pytest

from applytrail.lookup import NumberedApplication, numbered
from applytrail.models import Application, Store
from tests.fakes import load_store_fixture


def app(company, role, day):
    when = datetime(2026, 10, day, 12, 0, tzinfo=UTC)
    return Application(
        key=f"{company.casefold()}|{role.casefold()}",
        company=company,
        role=role,
        status="applied",
        last_activity=when,
        first_seen=when,
        thread_id=f"thr-{company}-{role}",
        subject="Your application",
        evidence="We received your application",
        message_ids=[f"msg-{company}-{role}"],
    )


def store_with(*apps: Application) -> Store:
    data = Store.empty()
    data.applications = {a.key: a for a in apps}
    return data


def test_empty_store_has_no_rows():
    assert numbered(Store.empty()) == []


def test_numbers_are_one_based_newest_first_then_company_then_role():
    data = store_with(
        app("beta", "Zeta Role", 3),
        app("Alpha", "Role B", 3),
        app("alpha", "Role A", 3),
        app("Newest", "Role", 9),
        app("Oldest", "Role", 1),
    )
    rows = numbered(data)
    assert [r.number for r in rows] == [1, 2, 3, 4, 5]
    assert [(r.app.company, r.app.role) for r in rows] == [
        ("Newest", "Role"),
        ("alpha", "Role A"),
        ("Alpha", "Role B"),
        ("beta", "Zeta Role"),
        ("Oldest", "Role"),
    ]


def test_numbering_is_stable_across_calls():
    data = load_store_fixture("store_lookup.json")
    assert numbered(data) == numbered(data)


def test_fixture_rows_match_the_documented_numbers():
    rows = numbered(load_store_fixture("store_lookup.json"))
    assert [(r.number, r.app.company, r.app.role) for r in rows] == [
        (1, "Acme Inc.", "Backend Engineer"),
        (2, "Google", "Software Engineer"),
        (3, "Globex International", None),
        (4, "[bold]Evil[/bold]", "Engineer"),
        (5, "Acme Inc.", "Data Engineer"),
        (6, "Northwind Traders", "Analyst"),
        (7, "Brightwave Labs", "QA Engineer"),
    ]


def test_numbered_application_is_frozen():
    row = NumberedApplication(number=1, app=app("Acme", "Engineer", 1))
    with pytest.raises(AttributeError):
        row.number = 2
