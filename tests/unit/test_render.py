"""Table, summary and lookup rendering (T030, T014, T023; contracts/cli.md)."""

import time
from datetime import UTC, datetime, timedelta

import pytest
from rich.console import Console

from applytrail.lookup import LookupResult, NumberedApplication, Suggestion, find, numbered
from applytrail.models import Application, RunCounts, Store
from applytrail.render import (
    build_check_table,
    build_table,
    render_found,
    render_not_found,
    render_open,
    render_summary,
    render_table,
)
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


# --- check output (T014, contracts/cli.md `check`) ---


@pytest.fixture
def utc(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def lookup_store() -> Store:
    return load_store_fixture("store_lookup.json")


def found_text(text: str, data: Store | None = None) -> str:
    data = data or lookup_store()
    out = console()
    render_found(find(data, text), data, out)
    return out.export_text()


def not_found_text(result: LookupResult, data: Store | None = None) -> str:
    out = console()
    render_not_found(result, data or lookup_store(), out)
    return out.export_text()


def test_check_table_columns():
    data = lookup_store()
    columns = build_check_table(data, numbered(data)).columns
    assert [c.header for c in columns] == [
        "#",
        "First seen",
        "Company",
        "Role",
        "Status",
        "Last seen",
    ]
    assert [c.width or c.max_width for c in columns] == [1, 10, 25, 21, 12, 10]


def test_found_header_and_rows_with_original_numbers(utc):
    text = found_text("acme")
    lines = text.splitlines()
    assert lines[0] == 'Found 2 applications matching "acme":'
    rows = body_lines(text)
    assert [[cell.strip() for cell in r.split("│")[1:-1]] for r in rows] == [
        ["1", "2026-09-30", "Acme Inc.", "Backend Engineer", "Interview", "2026-10-12"],
        ["5", "2026-08-20", "Acme Inc.", "Data Engineer", "Rejected", "2026-09-02"],
    ]
    assert "NEW" not in text and "UPD" not in text


def test_found_one_application_is_singular():
    assert found_text("google").splitlines()[0] == 'Found 1 application matching "google":'


def test_found_quotes_raw_input_literally():
    data = lookup_store()
    out = console()
    render_found(find(data, "[bold]evil[/bold]"), data, out)
    assert out.export_text().splitlines()[0] == (
        'Found 1 application matching "[bold]evil[/bold]":'
    )


def test_check_table_first_seen_is_local_date(monkeypatch):
    late = app("Acme", "Engineer", day=9).model_copy(
        update={"first_seen": datetime(2026, 10, 1, 20, 0, tzinfo=UTC)}
    )
    data = store_with(late)
    monkeypatch.setenv("TZ", "Pacific/Auckland")
    time.tzset()
    try:
        out = console()
        render_found(find(data, "acme"), data, out)
    finally:
        monkeypatch.undo()
        time.tzset()
    # 2026-10-01 20:00 UTC is 2026-10-02 09:00 in Auckland.
    assert body_lines(out.export_text())[0].split("│")[2].strip() == "2026-10-02"


def test_check_table_with_long_names_fits_100_columns():
    apps = [app(f"{i:03d}" + "C" * 80, "R" * 80, thread=f"t{i}") for i in range(999)]
    data = store_with(*apps)
    out = console()
    render_found(find(data, "001"), data, out)
    text = out.export_text()
    assert all(len(line) <= 100 for line in text.splitlines())
    row = body_lines(text)[0]
    assert len(row.split("│")[4].strip()) <= 21
    assert row.split("│")[4].strip().endswith("…")


def test_not_found_with_suggestion_and_last_sync(utc):
    assert not_found_text(find(lookup_store(), "Gogle")).splitlines() == [
        'No application found for "Gogle".',
        "Did you mean: Google (#2)?",
        "Last sync: 2026-10-14 08:02 (complete)",
    ]


def test_not_found_lists_every_number_and_several_suggestions(utc):
    result = LookupResult(
        query="Acmee",
        matches=[],
        suggestions=[Suggestion("Acme Inc.", [1, 5], 0.9), Suggestion("Google", [2], 0.8)],
    )
    assert (
        not_found_text(result).splitlines()[1] == "Did you mean: Acme Inc. (#1, #5), Google (#2)?"
    )


def test_not_found_without_suggestions_has_no_did_you_mean(utc):
    assert not_found_text(find(lookup_store(), "Initech")).splitlines() == [
        'No application found for "Initech".',
        "Last sync: 2026-10-14 08:02 (complete)",
    ]


@pytest.mark.parametrize(
    ("fields", "line"),
    [
        (
            {"last_sync_complete": False, "pending": 230},
            "Last sync: 2026-10-14 08:02 (incomplete — 230 emails pending; "
            "run applytrail to continue)",
        ),
        (
            {"last_sync_complete": False, "pending": 0},
            "Last sync: 2026-10-14 08:02 (incomplete; run applytrail to continue)",
        ),
        ({"last_sync_at": None}, "No sync has run yet."),
    ],
)
def test_not_found_last_sync_wording(utc, fields, line):
    data = lookup_store()
    for name, value in fields.items():
        setattr(data.sync, name, value)
    assert not_found_text(find(data, "Initech"), data).splitlines()[-1] == line


def test_not_found_quotes_raw_input_literally():
    result = LookupResult(query="[bold]x[/bold]", matches=[], suggestions=[])
    assert not_found_text(result).splitlines()[0] == 'No application found for "[bold]x[/bold]".'


def test_suggestion_company_is_not_markup():
    result = LookupResult(
        query="evl", matches=[], suggestions=[Suggestion("[bold]Evil[/bold]", [4], 0.8)]
    )
    assert not_found_text(result).splitlines()[1] == "Did you mean: [bold]Evil[/bold] (#4)?"


# --- open output (T023, contracts/cli.md `open`) ---

URL = "https://mail.google.com/mail/u/0/#all/18c0aa01"


def open_lines(row: NumberedApplication, launching: bool, width: int = 100) -> list[str]:
    out = Console(record=True, width=width)
    render_open(row, URL, launching, out)
    return out.export_text().splitlines()


def acme_row() -> NumberedApplication:
    return numbered(lookup_store())[0]


def test_open_line_when_launching():
    assert open_lines(acme_row(), launching=True) == [
        "Opening Acme Inc. — Backend Engineer (#1)",
        URL,
    ]


def test_address_for_line_when_not_launching():
    assert open_lines(acme_row(), launching=False)[0] == (
        "Address for Acme Inc. — Backend Engineer (#1)"
    )


def test_open_null_role_prints_unknown():
    globex = numbered(lookup_store())[2]
    assert open_lines(globex, launching=True)[0] == "Opening Globex International — Unknown (#3)"


def test_open_address_is_never_broken_across_lines():
    long_url = URL + "x" * 80
    out = Console(record=True, width=40)
    render_open(acme_row(), long_url, False, out)
    assert long_url in out.export_text().splitlines()


def test_open_company_is_not_markup():
    evil = numbered(lookup_store())[3]
    assert open_lines(evil, launching=True)[0] == "Opening [bold]Evil[/bold] — Engineer (#4)"


# --- synced mailbox links (T037) ---


def test_company_link_uses_the_synced_mailbox():
    data = store_with(app(thread="18c0aa01"))
    data.sync.mailbox = "me+jobs@example.com"
    out = console()
    render_table(data, out)
    html = out.export_html()
    assert 'href="https://mail.google.com/mail/u/me%2Bjobs@example.com/#all/18c0aa01"' in html
    assert "/u/0/" not in html


def test_check_table_link_uses_the_synced_mailbox():
    data = lookup_store()
    data.sync.mailbox = "me+jobs@example.com"
    out = console()
    render_found(find(data, "google"), data, out)
    assert "mail/u/me%2Bjobs@example.com/#all/18c0aa02" in out.export_html()
