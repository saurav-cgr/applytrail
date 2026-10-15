"""Row numbers and company lookup over the saved store (research R3–R5).

Row numbers are 1-based positions in the table's newest-first order, so the number a user
reads in the table is the number `open` accepts.
"""

from dataclasses import dataclass

from applytrail.models import Application, Store


def sort_key(app: Application) -> tuple:
    """Newest first, then company and role A to Z (data-model.md "Ordering")."""
    return (-app.last_activity.timestamp(), app.company.casefold(), (app.role or "").casefold())


@dataclass(frozen=True)
class NumberedApplication:
    number: int
    app: Application


def numbered(store: Store) -> list[NumberedApplication]:
    apps = sorted(store.applications.values(), key=sort_key)
    return [NumberedApplication(number=i, app=app) for i, app in enumerate(apps, start=1)]
