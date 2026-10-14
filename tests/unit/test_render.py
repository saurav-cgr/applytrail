"""Table and summary rendering (T030, contracts/cli.md "Table layout")."""

import time
from datetime import UTC, datetime

import pytest
from rich.console import Console

from applytrail.models import Application, RunCounts, Store
from applytrail.render import build_table, render_summary, render_table


def console(**kwargs) -> Console:
    return Console(record=True, width=100, **kwargs)


def app(company="Acme", role="Backend Engineer", status="applied", day=1, thread="thr-1"):
    when = datetime(2026, 10, day, 12, 0, tzinfo=UTC)
    return Application(
        key=f"{company.casefold()}|{(role or '').casefold()}",
        company=company,
        role=role,
        status=status,
        last_activity=when,
        first_seen=when,
        thread_id=thread,
        subject="Your application",
        evidence="We received your application",
        message_ids=[f"msg-{company}-{role}"],
    )


def store_with(*apps: Application) -> Store:
    data = Store.empty()
    data.applications = {a.key: a for a in apps}
    return data


def rendered(data: Store, **kwargs) -> str:
    out = console(**kwargs)
    render_table(data, out)
    return out.export_text()


def body_lines(text: str) -> list[str]:
    """Data rows: the `│` lines after the header separator."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("├"))
    return [line for line in lines[start:] if line.startswith("│")]


def test_columns_in_order():
    columns = build_table(store_with(app())).columns
    assert [c.header for c in columns] == ["", "Company", "Role", "Status", "Last seen"]


def test_rows_ordered_by_last_activity_then_company_then_role():
    data = store_with(
        app("beta", "Zeta Role", day=3),
        app("Alpha", "Role B", day=3),
        app("alpha", "Role A", day=3),
        app("Newest", "Role", day=9),
        app("Oldest", None, day=1),
    )
    rows = [
        line.split("│")[2].strip() + "/" + line.split("│")[3].strip()
        for line in body_lines(rendered(data))
    ]
    assert rows == [
        "Newest/Role",
        "alpha/Role A",
        "Alpha/Role B",
        "beta/Zeta Role",
        "Oldest/Unknown",
    ]


def test_long_names_are_ellipsized_within_100_columns():
    long = "X" * 80
    text = rendered(store_with(app(long, "Y" * 80)))
    assert all(len(line) <= 100 for line in text.splitlines())
    row = body_lines(text)[0].split("│")
    company, role = row[2].strip(), row[3].strip()
    assert company.endswith("…") and len(company) <= 28
    assert role.endswith("…") and len(role) <= 30


def test_column_widths():
    text = rendered(store_with(app("C" * 40, "R" * 40, status="in_review")))
    cells = body_lines(text)[0].split("│")[1:-1]
    widths = [len(cell) - 2 for cell in cells]  # one space of padding on each side
    assert widths == [4, 28, 30, 12, 10]


def test_null_role_shows_unknown():
    row = body_lines(rendered(store_with(app(role=None))))[0]
    assert row.split("│")[3].strip() == "Unknown"


@pytest.mark.parametrize("role", ["Engineer [/bad]", "[bold]Engineer[/bold]"])
def test_role_from_email_is_not_rich_markup(role):
    # Roles come from untrusted email text: brackets render literally, never as markup.
    row = body_lines(rendered(store_with(app(role=role))))[0]
    assert row.split("│")[3].strip() == role


@pytest.mark.parametrize(
    ("status", "label"),
    [
        ("applied", "Applied"),
        ("in_review", "In Review"),
        ("assessment", "Assessment"),
        ("interview", "Interview"),
        ("offer", "Offer"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ],
)
def test_status_is_text_without_colour(status, label):
    row = body_lines(rendered(store_with(app(status=status)), no_color=True))[0]
    assert row.split("│")[4].strip() == label


def test_last_activity_is_local_date(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    time.tzset()
    try:
        late = app()
        late.last_activity = datetime(2026, 10, 12, 23, 30, tzinfo=UTC)
        row = body_lines(rendered(store_with(late)))[0]
    finally:
        monkeypatch.undo()
        time.tzset()
    assert row.split("│")[5].strip() == "2026-10-13"


def test_company_links_to_the_gmail_thread():
    out = console()
    render_table(store_with(app(thread="18c2f0a1b2")), out)
    assert 'href="https://mail.google.com/mail/u/0/#all/18c2f0a1b2"' in out.export_html()


def test_badge_column_blank_without_badges():
    row = body_lines(rendered(store_with(app())))[0]
    assert row.split("│")[1].strip() == ""


def test_empty_store_prints_message():
    assert rendered(Store.empty()).strip() == "No job applications found yet."


def test_summary_line():
    out = console()
    render_summary(RunCounts(read=12, added=2, updated=1, ignored=8, skipped=1), out)
    assert out.export_text().strip() == "Read 12 emails · 2 new · 1 updated · 8 ignored · 1 skipped"


def test_header_fits_on_one_line():
    header = rendered(store_with(app())).split("├")[0]
    assert len([line for line in header.splitlines() if line.startswith("│")]) == 1
    assert "Last seen" in header
    assert "…" not in header
