"""Rich table and summary line (contracts/cli.md "Table layout", research R9).

Status and badges are always text; colour only reinforces them (FR-013).
"""

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from applytrail import links
from applytrail.lookup import NumberedApplication, numbered
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


def build_table(store: Store, rows: list[NumberedApplication] | None = None) -> Table:
    """The main table. `rows` defaults to every application; a subset keeps its numbers."""
    if rows is None:
        rows = numbered(store)
    table = Table(box=box.SQUARE)
    # `#` is as wide as the largest row number in the store, so a subset lines up the same.
    table.add_column("#", width=len(str(len(store.applications))), justify="right", no_wrap=True)
    table.add_column("", width=4, no_wrap=True)
    table.add_column("Company", max_width=25, no_wrap=True, overflow="ellipsis")
    table.add_column("Role", max_width=27, no_wrap=True, overflow="ellipsis")
    table.add_column("Status", width=12, no_wrap=True)
    table.add_column("Last seen", width=10, no_wrap=True)

    added, updated = set(store.sync.added), set(store.sync.updated)
    for row in rows:
        app = row.app
        badge = "NEW" if app.key in added else "UPD" if app.key in updated else ""
        link = links.thread_url(app.thread_id)
        table.add_row(
            Text(str(row.number)),
            Text(badge, style="bold"),
            Text(app.company, style=f"link {link}"),
            Text(app.role or "Unknown"),  # email text: never parsed as markup
            Text(app.status.label, style=_STATUS_STYLES[app.status]),
            app.last_activity.astimezone().strftime("%Y-%m-%d"),
        )
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


def render_last_sync(sync: SyncState, console: Console) -> None:
    """`--offline` footer: when the latest sync ran and whether it finished."""
    if sync.last_sync_at is None:
        return
    when = sync.last_sync_at.astimezone().strftime("%Y-%m-%d %H:%M")
    if sync.last_sync_complete:
        state = "complete"
    elif sync.pending:
        state = f"incomplete — {sync.pending} emails pending; run applytrail to continue"
    else:
        state = "incomplete; run applytrail to continue"
    console.print(f"Last sync: {when} ({state})", highlight=False, soft_wrap=True)
