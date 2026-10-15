"""Row numbers, lookup and suggestions (T004, T012, T013; research R3–R5)."""

import time
from datetime import UTC, datetime

import pytest

from applytrail.errors import InvalidInput
from applytrail.lookup import (
    SUGGEST_CUTOFF,
    LookupResult,
    NumberedApplication,
    Suggestion,
    find,
    normalize_query,
    numbered,
    resolve,
)
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


def lookup_store() -> Store:
    return load_store_fixture("store_lookup.json")


def found_numbers(text: str, data: Store | None = None) -> list[int]:
    return [r.number for r in find(data or lookup_store(), text).matches]


# --- normalize_query and find (T012, research R3) ---


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Acme & Co", ["acme"]),
        ("Acme, Inc.", ["acme"]),
        ("  Globex   International ", ["globex", "international"]),
        ("Johnson and", ["johnson"]),
        ("", []),
        ("   ", []),
        ("&", []),
    ],
)
def test_normalize_query(text, words):
    assert normalize_query(text) == words


@pytest.mark.parametrize("text", ["", "   ", "&", "!!", ",."])
def test_find_rejects_empty_or_punctuation_only_text(text):
    with pytest.raises(InvalidInput):
        find(lookup_store(), text)


@pytest.mark.parametrize("text", ["acme", "ACME", "Acme, Inc.", "acme corp", "Acme & Co"])
def test_acme_spellings_find_both_acme_rows_in_order(text):
    assert found_numbers(text) == [1, 5]


@pytest.mark.parametrize("text", ["glob", "globex", "international"])
def test_word_prefix_finds_globex(text):
    assert found_numbers(text) == [3]


@pytest.mark.parametrize("text", ["lob", "engineer", "Initech"])
def test_not_found(text):
    result = find(lookup_store(), text)
    assert result.matches == []
    assert result.found is False


def test_rejected_and_withdrawn_applications_are_found():
    assert found_numbers("acme")[-1] == 5  # rejected
    assert found_numbers("northwind") == [6]  # withdrawn


def test_display_company_and_key_company_both_match():
    renamed = app("Contoso Ltd", "Engineer", 5).model_copy(update={"key": "fabrikam|engineer"})
    data = store_with(renamed)
    assert found_numbers("contoso", data) == [1]
    assert found_numbers("fabrikam", data) == [1]


def test_lookup_result_fields_and_found():
    result = find(lookup_store(), "Acme")
    assert isinstance(result, LookupResult)
    assert result.query == "Acme"
    assert all(isinstance(m, NumberedApplication) for m in result.matches)
    assert result.found is True
    assert result.suggestions == []


# --- suggestions (T013, research R4) ---


def test_gogle_suggests_google_row_2():
    first = find(lookup_store(), "Gogle").suggestions[0]
    assert isinstance(first, Suggestion)
    assert (first.company, first.numbers) == ("Google", [2])
    assert first.score >= SUGGEST_CUTOFF


def test_suggestion_lists_every_row_of_a_company_ascending():
    first = find(lookup_store(), "Acmee").suggestions[0]
    assert (first.company, first.numbers) == ("Acme Inc.", [1, 5])


def test_suggestions_capped_at_3_by_score_then_company():
    data = store_with(
        app("Acmo", "R", 1),
        app("acma", "R", 2),
        app("Acmi", "R", 3),
        app("Acmeo", "R", 4),
        app("Bacmx Labs", "R", 5),
    )
    # "acmx": Bacmx scores 0.89; acma, Acmi and Acmo tie at 0.75; Acmeo is below the cutoff.
    suggestions = find(data, "acmx").suggestions
    assert [s.company for s in suggestions] == ["Bacmx Labs", "acma", "Acmi"]
    scores = [s.score for s in suggestions]
    assert scores == sorted(scores, reverse=True)


def test_no_suggestions_when_matches_exist():
    assert find(lookup_store(), "acme").suggestions == []


def test_no_suggestions_below_cutoff():
    assert SUGGEST_CUTOFF == 0.75
    assert find(lookup_store(), "Initech").suggestions == []


def test_lookup_is_deterministic():
    data = lookup_store()
    assert find(data, "Gogle") == find(data, "Gogle")
    assert find(data, "acme") == find(data, "acme")


# SC-003: spelling variants of saved companies are all found.
SC003_VARIANTS = [
    ("acme", [1, 5]),
    ("ACME", [1, 5]),
    ("Acme Inc.", [1, 5]),
    ("Acme, Inc.", [1, 5]),
    ("acme corp", [1, 5]),
    ("Acme & Co", [1, 5]),
    ("acme ltd", [1, 5]),
    ("  acme  ", [1, 5]),
    ("ac", [1, 5]),
    ("google", [2]),
    ("GOOGLE", [2]),
    ("Google LLC", [2]),
    ("goo", [2]),
    ("globex", [3]),
    ("Glob", [3]),
    ("Globex International", [3]),
    ("globex int", [3]),
    ("international", [3]),
    ("northwind", [6]),
    ("Northwind Traders", [6]),
    ("north", [6]),
    ("brightwave", [7]),
    ("Brightwave Labs, Inc.", [7]),
    ("bright", [7]),
    ("evil", [4]),
]

SC003_UNRELATED = [
    "Initech",
    "Umbrella",
    "Stark Industries",
    "Wayne Enterprises",
    "Cyberdyne",
    "Hooli",
    "Pied Piper",
    "Soylent",
    "Tyrell",
    "Wonka",
]


def test_sc003_variants_are_found():
    assert len(SC003_VARIANTS) >= 20
    data = lookup_store()
    misses = [(t, n) for t, n in SC003_VARIANTS if found_numbers(t, data) != n]
    assert misses == []


def test_sc003_unrelated_names_do_not_match():
    assert len(SC003_UNRELATED) == 10
    data = lookup_store()
    assert [t for t in SC003_UNRELATED if find(data, t).matches] == []


# SC-003a: one- or two-letter typos suggest the intended company.
SC003A_TYPOS = [
    ("Gogle", "Google"),
    ("Googel", "Google"),
    ("Gooogle", "Google"),
    ("Acmee", "Acme Inc."),
    ("Acne", "Acme Inc."),
    ("Globx", "Globex International"),
    ("Glbex", "Globex International"),
    ("Nortwind", "Northwind Traders"),
    ("Northwnd Traders", "Northwind Traders"),
    ("Brigthwave", "Brightwave Labs"),
    ("Brightwaev Labs", "Brightwave Labs"),
    ("Brihgtwave", "Brightwave Labs"),
]


def test_sc003a_typos_suggest_the_intended_company():
    assert len(SC003A_TYPOS) >= 10
    data = lookup_store()
    hits = 0
    for text, company in SC003A_TYPOS:
        result = find(data, text)
        assert result.matches == [], text
        hits += company in [s.company for s in result.suggestions]
    assert hits / len(SC003A_TYPOS) >= 0.9


def test_company_with_no_lookup_words_is_skipped_for_suggestions():
    # V-003: a stored company such as "And" normalizes to no words.
    data = store_with(app("And", "Engineer", 4), app("Google", "Engineer", 3))
    result = find(data, "Gogle")
    assert result.matches == []
    assert [s.company for s in result.suggestions] == ["Google"]
    assert find(data, "Initech").suggestions == []


# --- resolve (T022, contracts/cli.md `open`) ---


def test_resolve_single_number_returns_that_row():
    row = resolve(lookup_store(), ["2"])
    assert isinstance(row, NumberedApplication)
    assert (row.number, row.app.company) == (2, "Google")


@pytest.mark.parametrize("target", ["0", "99", "8"])
def test_resolve_number_out_of_range(target):
    with pytest.raises(InvalidInput) as raised:
        resolve(lookup_store(), [target])
    assert raised.value.message == (
        f"No row {target}. Choose a number from 1 to 7 (see applytrail --offline)."
    )


def test_resolve_name_returns_lookup_result():
    result = resolve(lookup_store(), ["acme", "corp"])
    assert isinstance(result, LookupResult)
    assert result.query == "acme corp"
    assert [r.number for r in result.matches] == [1, 5]


def test_resolve_several_targets_with_digits_are_a_name():
    result = resolve(lookup_store(), ["3", "acme"])
    assert isinstance(result, LookupResult)
    assert result.matches == []


@pytest.mark.parametrize("targets", [["&"], ["  "], [",", "."]])
def test_resolve_empty_name(targets):
    with pytest.raises(InvalidInput) as raised:
        resolve(lookup_store(), targets)
    assert raised.value.message == (
        "Enter a row number or company name, for example: applytrail open 3"
    )


def test_resolve_huge_number_is_out_of_range_not_a_crash():
    # V-006: Python refuses int() on digit strings over 4300 characters.
    target = "9" * 4500
    with pytest.raises(InvalidInput) as raised:
        resolve(lookup_store(), [target])
    assert raised.value.message == (
        f"No row {target}. Choose a number from 1 to 7 (see applytrail --offline)."
    )


@pytest.mark.parametrize("target", ["02", "0" * 4500 + "2"], ids=["02", "4500-zeros-2"])
def test_resolve_leading_zeros_pick_the_row(target):
    assert resolve(lookup_store(), [target]).number == 2


def test_resolve_all_zeros_is_out_of_range():
    with pytest.raises(InvalidInput):
        resolve(lookup_store(), ["0" * 4500])


# --- Performance (T045, SC-002) ----------------------------------------------------------------


PERF_ROWS = 500
PERF_LIMIT_SECONDS = 1.0


def perf_store(n: int) -> Store:
    data = Store.empty()
    for i in range(n):
        company = "Acme Inc." if i % 50 == 0 else f"Company {i:03d} Holdings"
        role = f"Engineer {i}"
        a = app(company, role, 1 + i % 28)
        data.applications[a.key] = a
    return data


@pytest.mark.parametrize(
    "action",
    [
        lambda data: numbered(data),
        lambda data: find(data, "acme"),
        lambda data: find(data, "zzzz"),
        lambda data: resolve(data, ["250"]),
    ],
    ids=["numbered", "find-hit", "find-miss", "resolve-number"],
)
def test_lookup_on_500_applications_is_under_a_second(action):
    data = perf_store(PERF_ROWS)
    assert len(data.applications) == PERF_ROWS

    started = time.perf_counter()
    result = action(data)
    elapsed = time.perf_counter() - started

    assert result is not None
    assert elapsed < PERF_LIMIT_SECONDS, f"{elapsed:.3f} s for {PERF_ROWS} applications"
