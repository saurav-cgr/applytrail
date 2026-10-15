"""Table and summary rendering (T030, contracts/cli.md "Table layout")."""

import time
from datetime import UTC, datetime, timedelta

import pytest
from rich.console import Console

from applytrail.lookup import numbered
from applytrail.models import Application, RunCounts, Store
from applytrail.render import build_table, render_summary, render_table
from tests.fakes import load_store_fixture


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
    assert [c.header for c in columns] == ["#", "", "Company", "Role", "Status", "Last seen"]


def test_rows_ordered_by_last_activity_then_company_then_role():
    data = store_with(
        app("beta", "Zeta Role", day=3),
        app("Alpha", "Role B", day=3),
        app("alpha", "Role A", day=3),
        app("Newest", "Role", day=9),
        app("Oldest", None, day=1),
    )
    rows = [
        line.split("│")[3].strip() + "/" + line.split("│")[4].strip()
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
    company, role = row[3].strip(), row[4].strip()
    assert company.endswith("…") and len(company) <= 25
    assert role.endswith("…") and len(role) <= 27


def test_column_widths():
    text = rendered(store_with(app("C" * 40, "R" * 40, status="in_review")))
    cells = body_lines(text)[0].split("│")[1:-1]
    widths = [len(cell) - 2 for cell in cells]  # one space of padding on each side
    assert widths == [1, 4, 25, 27, 12, 10]


def test_number_column_is_as_wide_as_the_row_count():
    apps = [app(f"C{i:02d}", "Role", thread=f"t{i}") for i in range(12)]
    cells = body_lines(rendered(store_with(*apps)))[0].split("│")[1:-1]
    assert len(cells[0]) - 2 == 2


def test_null_role_shows_unknown():
    row = body_lines(rendered(store_with(app(role=None))))[0]
    assert row.split("│")[4].strip() == "Unknown"


@pytest.mark.parametrize("role", ["Engineer [/bad]", "[bold]Engineer[/bold]"])
def test_role_from_email_is_not_rich_markup(role):
    # Roles come from untrusted email text: brackets render literally, never as markup.
    row = body_lines(rendered(store_with(app(role=role))))[0]
    assert row.split("│")[4].strip() == role


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
    assert row.split("│")[5].strip() == label


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
    assert row.split("│")[6].strip() == "2026-10-13"


def test_company_links_to_the_gmail_thread():
    out = console()
    render_table(store_with(app(thread="18c2f0a1b2")), out)
    assert 'href="https://mail.google.com/mail/u/0/#all/18c2f0a1b2"' in out.export_html()


def test_badge_column_blank_without_badges():
    row = body_lines(rendered(store_with(app())))[0]
    assert row.split("│")[2].strip() == ""


def test_badges_are_text_without_colour():
    added, updated, plain = app("Acme", day=3), app("Globex", day=2), app("Initech", day=1)
    data = store_with(added, updated, plain)
    data.sync.added = [added.key]
    data.sync.updated = [updated.key]

    rows = body_lines(rendered(data, no_color=True))

    assert [r.split("│")[2].strip() for r in rows] == ["NEW", "UPD", ""]
    assert [r.split("│")[3].strip() for r in rows] == ["Acme", "Globex", "Initech"]


def test_second_sync_with_no_changes_shows_no_badges(tmp_path, monkeypatch):
    # US2 scenario 3: the run that finds nothing new clears the previous run's badges.
    from applytrail import sync
    from applytrail.config import Settings
    from tests.fakes import FakeExtractor, FakeMcpClient, load_fixture

    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path))
    settings = Settings.from_env()
    fixtures = [load_fixture("confirm_acme_backend")]
    data = Store.empty()
    now = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    for run_at in (now, now + timedelta(days=1)):
        sync.run_sync(data, FakeMcpClient(fixtures), FakeExtractor(fixtures), settings, run_at)
        badges = [r.split("│")[2].strip() for r in body_lines(rendered(data))]
        if run_at == now:
            assert badges == ["NEW"]

    assert badges == [""]


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


def test_999_rows_with_long_names_fit_100_columns_without_wrapping():
    apps = [app(f"{i:03d}" + "C" * 80, "R" * 80, thread=f"t{i}") for i in range(999)]
    text = rendered(store_with(*apps))
    assert all(len(line) <= 100 for line in text.splitlines())
    assert len(body_lines(text)) == 999


def test_row_numbers_are_plain_right_aligned_text():
    apps = [app(f"C{i:02d}", "Role", thread=f"t{i}") for i in range(10)]
    rows = body_lines(rendered(store_with(*apps), no_color=True))
    assert [r.split("│")[1] for r in rows[:2]] == ["  1 ", "  2 "]
    assert rows[9].split("│")[1] == " 10 "


def test_subset_keeps_original_numbers():
    data = load_store_fixture("store_lookup.json")
    subset = [r for r in numbered(data) if r.number in (1, 5)]
    out = console()
    out.print(build_table(data, rows=subset))
    rows = body_lines(out.export_text())
    assert [(r.split("│")[1].strip(), r.split("│")[4].strip()) for r in rows] == [
        ("1", "Backend Engineer"),
        ("5", "Data Engineer"),
    ]


def test_company_from_email_is_not_rich_markup():
    row = body_lines(rendered(store_with(app("[bold]Evil[/bold]", "Engineer"))))[0]
    assert row.split("│")[3].strip() == "[bold]Evil[/bold]"
