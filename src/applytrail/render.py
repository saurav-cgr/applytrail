"""Rich tables, summary line and lookup answers (contracts/cli.md, research R9).

Status and badges are always text; colour only reinforces them (FR-013).
"""

from datetime import datetime

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from applytrail import links
from applytrail.lookup import LookupResult, NumberedApplication, numbered
from applytrail.lookup import sort_key as sort_key  # re-exported for callers of render.sort_key
from applytrail.models import RunCounts, Status, Store, SyncState

EMPTY_MESSAGE = "No job applications found yet."

_STATUS_STYLES = {
    Status.APPLIED: "cyan",
    Status.IN_REVIEW: "blue",
    Status.ASSESSMENT: "magenta",
    Status.INTERVIEW: "yellow",
    Status.OFFER: "bold green",
    Status.REJECTED: "red",
    Status.WITHDRAWN: "dim",
}


def _local_date(when: datetime) -> str:
    return when.astimezone().strftime("%Y-%m-%d")


def _new_table(store: Store, second: tuple[str, int], role_width: int) -> Table:
    """Columns shared by the main and `check` tables; `second` is (header, width)."""
    table = Table(box=box.SQUARE)
    # `#` is as wide as the largest row number in the store, so a subset lines up the same.
    table.add_column("#", width=len(str(len(store.applications))), justify="right", no_wrap=True)
    table.add_column(second[0], width=second[1], no_wrap=True)
    table.add_column("Company", max_width=25, no_wrap=True, overflow="ellipsis")
    table.add_column("Role", max_width=role_width, no_wrap=True, overflow="ellipsis")
    table.add_column("Status", width=12, no_wrap=True)
    table.add_column("Last seen", width=10, no_wrap=True)
    return table


def _add_row(table: Table, row: NumberedApplication, second: Text | str) -> None:
    app = row.app
    link = links.thread_url(app.thread_id)
    table.add_row(
        Text(str(row.number)),
        second,
        Text(app.company, style=f"link {link}"),
        Text(app.role or "Unknown"),  # email text: never parsed as markup
        Text(app.status.label, style=_STATUS_STYLES[app.status]),
        _local_date(app.last_activity),
    )


def build_table(store: Store, rows: list[NumberedApplication] | None = None) -> Table:
    """The main table. `rows` defaults to every application; a subset keeps its numbers."""
    if rows is None:
        rows = numbered(store)
    table = _new_table(store, ("", 4), role_width=27)
    added, updated = set(store.sync.added), set(store.sync.updated)
    for row in rows:
        key = row.app.key
        badge = "NEW" if key in added else "UPD" if key in updated else ""
        _add_row(table, row, Text(badge, style="bold"))
    return table


def build_check_table(store: Store, rows: list[NumberedApplication]) -> Table:
    """The `check` table: First seen replaces the badge column; Role narrows (FR-004)."""
    table = _new_table(store, ("First seen", 10), role_width=21)
    for row in rows:
        _add_row(table, row, _local_date(row.app.first_seen))
    return table


def render_table(store: Store, console: Console) -> None:
    if not store.applications:
        console.print(EMPTY_MESSAGE)
        return
    console.print(build_table(store))


def render_summary(counts: RunCounts, console: Console) -> None:
    console.print(
        f"Read {counts.read} emails · {counts.added} new · {counts.updated} updated · "
        f"{counts.ignored} ignored · {counts.skipped} skipped",
        highlight=False,
    )


def last_sync_line(sync: SyncState) -> str | None:
    """When the latest sync ran and whether it finished; None before the first sync."""
    if sync.last_sync_at is None:
        return None
    when = sync.last_sync_at.astimezone().strftime("%Y-%m-%d %H:%M")
    if sync.last_sync_complete:
        state = "complete"
    elif sync.pending:
        state = f"incomplete — {sync.pending} emails pending; run applytrail to continue"
    else:
        state = "incomplete; run applytrail to continue"
    return f"Last sync: {when} ({state})"


def render_last_sync(sync: SyncState, console: Console) -> None:
    """`--offline` footer."""
    line = last_sync_line(sync)
    if line is not None:
        _plain(console, line)


def render_found(result: LookupResult, store: Store, console: Console) -> None:
    count = len(result.matches)
    noun = "application" if count == 1 else "applications"
    _plain(console, f'Found {count} {noun} matching "{result.query}":')
    console.print(build_check_table(store, result.matches))


def render_not_found(result: LookupResult, store: Store, console: Console) -> None:
    _plain(console, f'No application found for "{result.query}".')
    if result.suggestions:
        names = ", ".join(
            f"{s.company} ({', '.join(f'#{n}' for n in s.numbers)})" for s in result.suggestions
        )
        _plain(console, f"Did you mean: {names}?")
    _plain(console, last_sync_line(store.sync) or "No sync has run yet.")


def render_open(row: NumberedApplication, url: str, launching: bool, console: Console) -> None:
    """What is being opened, then the address alone on its own unbroken line (research R9)."""
    verb = "Opening" if launching else "Address for"
    _plain(console, f"{verb} {row.app.company} — {row.app.role or 'Unknown'} (#{row.number})")
    _plain(console, url)


def _plain(console: Console, text: str) -> None:
    """One line printed literally: user and email text is never Rich markup."""
    console.print(text, markup=False, highlight=False, soft_wrap=True)
