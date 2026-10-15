"""Row numbers and company lookup over the saved store (research R3–R5).

Row numbers are 1-based positions in the table's newest-first order, so the number a user
reads in the table is the number `open` accepts.
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from applytrail.errors import InvalidInput
from applytrail.models import Application, Store
from applytrail.normalize import norm_company

CHECK_EMPTY_MESSAGE = "Enter a company name, for example: applytrail check acme"
SUGGEST_CUTOFF = 0.75
MAX_SUGGESTIONS = 3


def sort_key(app: Application) -> tuple:
    """Newest first, then company and role A to Z (data-model.md "Ordering")."""
    return (-app.last_activity.timestamp(), app.company.casefold(), (app.role or "").casefold())


@dataclass(frozen=True)
class NumberedApplication:
    number: int
    app: Application


@dataclass(frozen=True)
class Suggestion:
    company: str
    numbers: list[int]
    score: float


@dataclass(frozen=True)
class LookupResult:
    query: str
    matches: list[NumberedApplication]
    suggestions: list[Suggestion] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.matches)


def numbered(store: Store) -> list[NumberedApplication]:
    apps = sorted(store.applications.values(), key=sort_key)
    return [NumberedApplication(number=i, app=app) for i, app in enumerate(apps, start=1)]


def normalize_query(text: str) -> list[str]:
    """`norm_company` words, minus one trailing "and" ("Acme & Co" -> ["acme"])."""
    words = norm_company(text).split()
    if words and words[-1] == "and":
        words.pop()
    return words


def _company_words(app: Application) -> tuple[list[str], list[str]]:
    """The display company and the key's company part, each normalized like a query."""
    return normalize_query(app.company), normalize_query(app.key.split("|", 1)[0])


def _contains(words: list[str], query: list[str]) -> bool:
    """`query` is a consecutive run of `words`; its last word may be a prefix."""
    n = len(query)
    for i in range(len(words) - n + 1):
        run = words[i : i + n]
        if run[:-1] == query[:-1] and run[-1].startswith(query[-1]):
            return True
    return False


def _score(query: str, n: int, words: list[str]) -> float:
    """Best ratio against the whole name or any run of `n` words in it."""
    candidates = {" ".join(words)}
    candidates.update(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))
    return max(SequenceMatcher(None, query, c).ratio() for c in candidates if c)


def _suggest(rows: list[NumberedApplication], query: list[str]) -> list[Suggestion]:
    text = " ".join(query)
    by_company: dict[str, list[NumberedApplication]] = {}
    for row in rows:
        by_company.setdefault(row.app.key.split("|", 1)[0], []).append(row)
    suggestions = []
    for group in by_company.values():
        # A company that normalizes to no words (for example "And") can't be suggested.
        scores = [_score(text, len(query), w) for w in _company_words(group[0].app) if w]
        score = max(scores, default=0.0)
        if score >= SUGGEST_CUTOFF:
            # Rows are newest first, so group[0] holds the newest display spelling.
            numbers = [r.number for r in group]
            suggestions.append(Suggestion(group[0].app.company, numbers, score))
    suggestions.sort(key=lambda s: (-s.score, s.company.casefold()))
    return suggestions[:MAX_SUGGESTIONS]


def find(store: Store, text: str, empty_message: str = CHECK_EMPTY_MESSAGE) -> LookupResult:
    """Applications whose company matches `text`; suggestions only when nothing matches."""
    query = normalize_query(text)
    if not query:
        raise InvalidInput(empty_message)
    rows = numbered(store)
    matches = [r for r in rows if any(_contains(w, query) for w in _company_words(r.app))]
    suggestions = [] if matches else _suggest(rows, query)
    return LookupResult(query=text, matches=matches, suggestions=suggestions)
