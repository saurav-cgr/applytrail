"""Rich table and summary line (contracts/cli.md "Table layout", research R9).

Status and badges are always text; colour only reinforces them (FR-013).
"""

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from applytrail.models import Application, RunCounts, Status, Store, SyncState

GMAIL_THREAD_URL = "https://mail.google.com/mail/u/0/#all/{thread_id}"
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


def sort_key(app: Application) -> tuple:
    """Newest first, then company and role A to Z (data-model.md "Ordering")."""
    return (-app.last_activity.timestamp(), app.company.casefold(), (app.role or "").casefold())


def build_table(store: Store) -> Table:
    table = Table(box=box.SQUARE)
    table.add_column("", width=4, no_wrap=True)
    table.add_column("Company", max_width=28, no_wrap=True, overflow="ellipsis")
    table.add_column("Role", max_width=30, no_wrap=True, overflow="ellipsis")
    table.add_column("Status", width=12, no_wrap=True)
    table.add_column("Last seen", width=10, no_wrap=True)

    added, updated = set(store.sync.added), set(store.sync.updated)
    for app in sorted(store.applications.values(), key=sort_key):
        badge = "NEW" if app.key in added else "UPD" if app.key in updated else ""
        link = GMAIL_THREAD_URL.format(thread_id=app.thread_id)
        table.add_row(
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
