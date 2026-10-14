"""Merge rules 1-3 and the outcome rules (data-model.md "Merge rules"). Pure, no I/O."""

from datetime import UTC, datetime

import pytest

from applytrail import merge
from applytrail.errors import ExtractionInvalid
from applytrail.models import Extraction, ProcessedEmail, Status, Store
from tests.fakes import email_meta, load_fixture


def pair(name, **expected_overrides):
    fixture = load_fixture(name)
    extraction = Extraction.model_validate({**fixture["expected"], **expected_overrides})
    return extraction, email_meta(fixture)


def extraction(company="Acme Inc.", role="Backend Engineer", status="applied", evidence="ok"):
    return Extraction(
        is_job_application=True, company=company, role=role, status=status, evidence=evidence
    )


def email(mid, when, subject="Subject", thread=None):
    return email_meta(
        {
            "message_id": mid,
            "thread_id": thread or f"thread-{mid}",
            "date": when,
            "sender": "jobs@acme.example",
            "subject": subject,
            "body_text": "body",
        }
    )


def apply_all(store, *pairs):
    return [merge.apply(store, e, m) for e, m in pairs]


def comparable(app):
    data = app.model_dump()
    data["message_ids"] = sorted(data["message_ids"])
    return data


# --- classify ---------------------------------------------------------------------------------


def test_classify_usable():
    assert merge.classify(extraction()) == ("applied", None)


def test_classify_not_a_job():
    e = Extraction(is_job_application=False, company="", role=None, status="unknown", evidence="")
    assert merge.classify(e) == ("ignored", None)


def test_classify_not_a_job_wins_even_with_company():
    e = extraction()
    e = e.model_copy(update={"is_job_application": False})
    assert merge.classify(e) == ("ignored", None)


@pytest.mark.parametrize(
    "e",
    [extraction(company=""), extraction(company="   "), extraction(status="unknown")],
    ids=["empty-company", "blank-company", "unknown-status"],
)
def test_classify_incomplete(e):
    assert merge.classify(e) == ("skipped", "incomplete")


def test_classify_invalid_output():
    assert merge.classify(None) == ("skipped", "invalid_output")
    assert merge.classify(ExtractionInvalid("bad")) == ("skipped", "invalid_output")


# --- rule 3: status over time -----------------------------------------------------------------


def test_confirmation_then_rejection():
    store = Store.empty()
    results = apply_all(store, pair("confirm_acme_backend"), pair("reject_acme_backend"))
    assert [r.key for r in results] == ["acme|backend engineer"] * 2
    assert [r.created for r in results] == [True, False]

    app = store.applications["acme|backend engineer"]
    assert len(store.applications) == 1
    assert app.status is Status.REJECTED
    assert app.last_activity == datetime(2026, 10, 12, 14, 3, tzinfo=UTC)
    assert app.first_seen == datetime(2026, 9, 30, 8, 11, tzinfo=UTC)
    assert app.message_ids == ["msg-acme-001", "msg-acme-004"]
    assert app.subject == "Your application to Acme Inc."
    assert app.evidence == "we have decided not to move forward with your application"


def test_newest_first_order_gives_same_final_state():
    forward, backward = Store.empty(), Store.empty()
    apply_all(forward, pair("confirm_acme_backend"), pair("reject_acme_backend"))
    apply_all(backward, pair("reject_acme_backend"), pair("confirm_acme_backend"))
    assert forward.applications.keys() == backward.applications.keys()
    for key in forward.applications:
        assert comparable(forward.applications[key]) == comparable(backward.applications[key])
    assert backward.applications["acme|backend engineer"].message_ids == [
        "msg-acme-004",
        "msg-acme-001",
    ]


def test_older_email_never_overwrites_newer_status():
    store = Store.empty()
    apply_all(store, pair("confirm_acme_backend"), pair("reject_acme_backend"))
    before = store.applications["acme|backend engineer"].model_copy()
    result = merge.apply(store, *pair("delayed_old_email"))
    app = store.applications["acme|backend engineer"]
    assert result.created is False
    assert app.status is Status.REJECTED
    assert app.last_activity == before.last_activity
    assert app.subject == before.subject
    assert app.evidence == before.evidence
    assert app.thread_id == before.thread_id
    assert app.company == before.company
    assert "msg-acme-003" in app.message_ids


def test_same_date_counts_as_newer():
    store = Store.empty()
    when = "2026-10-01T10:00:00Z"
    merge.apply(store, extraction(status="applied"), email("a", when))
    merge.apply(store, extraction(status="interview"), email("b", when))
    assert store.applications["acme|backend engineer"].status is Status.INTERVIEW


def test_reapplying_same_message_does_not_duplicate_id():
    store = Store.empty()
    e, m = pair("confirm_acme_backend")
    merge.apply(store, e, m)
    merge.apply(store, e, m)
    assert store.applications["acme|backend engineer"].message_ids == ["msg-acme-001"]


# --- rule 1: role given -----------------------------------------------------------------------


def test_same_company_two_roles_are_separate():
    store = Store.empty()
    merge.apply(store, extraction(role="Backend Engineer"), email("a", "2026-10-01T10:00:00Z"))
    merge.apply(store, extraction(role="Data Engineer"), email("b", "2026-10-02T10:00:00Z"))
    assert set(store.applications) == {"acme|backend engineer", "acme|data engineer"}


def test_role_given_fills_in_single_unknown_role_and_rekeys():
    store = Store.empty()
    first = merge.apply(store, extraction(role=None), email("a", "2026-10-01T10:00:00Z"))
    store.processed["a"] = ProcessedEmail(
        message_id="a",
        date=datetime(2026, 10, 1, 10, tzinfo=UTC),
        outcome="applied",
        application_key=first.key,
    )
    assert first.key == "acme|"

    result = merge.apply(
        store,
        extraction(role="Backend Engineer", status="interview"),
        email("b", "2026-10-03T10:00:00Z"),
    )

    assert result.key == "acme|backend engineer"
    assert result.created is False
    assert result.rekeyed_from == "acme|"
    assert set(store.applications) == {"acme|backend engineer"}
    app = store.applications["acme|backend engineer"]
    assert app.key == "acme|backend engineer"
    assert app.role == "Backend Engineer"
    assert app.status is Status.INTERVIEW
    assert app.message_ids == ["a", "b"]
    assert store.processed["a"].application_key == "acme|backend engineer"


def test_rekey_fills_role_even_from_older_email():
    store = Store.empty()
    merge.apply(
        store, extraction(role=None, status="interview"), email("a", "2026-10-05T10:00:00Z")
    )
    merge.apply(store, extraction(role="Backend Engineer"), email("b", "2026-10-01T10:00:00Z"))
    app = store.applications["acme|backend engineer"]
    assert app.role == "Backend Engineer"
    assert app.status is Status.INTERVIEW  # older email: no status change


def test_role_given_with_unknown_role_and_another_role_creates_new():
    store = Store.empty()
    merge.apply(store, extraction(role="Data Engineer"), email("a", "2026-10-01T10:00:00Z"))
    store.applications["acme|"] = store.applications["acme|data engineer"].model_copy(
        update={"key": "acme|", "role": None, "message_ids": ["z"]}
    )
    result = merge.apply(
        store, extraction(role="Backend Engineer"), email("b", "2026-10-02T10:00:00Z")
    )
    assert result.created is True
    assert set(store.applications) == {"acme|", "acme|data engineer", "acme|backend engineer"}


def test_role_given_existing_key_is_targeted_even_with_other_roles():
    store = Store.empty()
    merge.apply(store, extraction(role="Backend Engineer"), email("a", "2026-10-01T10:00:00Z"))
    merge.apply(store, extraction(role="Data Engineer"), email("b", "2026-10-02T10:00:00Z"))
    result = merge.apply(
        store,
        extraction(role="Backend Engineer", status="offer"),
        email("c", "2026-10-03T10:00:00Z"),
    )
    assert result.key == "acme|backend engineer"
    assert store.applications["acme|backend engineer"].status is Status.OFFER


# --- rule 2: role missing ---------------------------------------------------------------------


def test_role_missing_targets_the_only_application():
    store = Store.empty()
    merge.apply(store, extraction(role="Backend Engineer"), email("a", "2026-10-01T10:00:00Z"))
    result = merge.apply(
        store, extraction(role=None, status="rejected"), email("b", "2026-10-02T10:00:00Z")
    )
    assert result.key == "acme|backend engineer"
    app = store.applications["acme|backend engineer"]
    assert app.status is Status.REJECTED
    assert app.role == "Backend Engineer"  # a missing role never erases a known one


def test_role_missing_with_two_applications_creates_unknown_role():
    store = Store.empty()
    merge.apply(store, extraction(role="Backend Engineer"), email("a", "2026-10-01T10:00:00Z"))
    merge.apply(store, extraction(role="Data Engineer"), email("b", "2026-10-02T10:00:00Z"))
    result = merge.apply(store, extraction(role=None), email("c", "2026-10-03T10:00:00Z"))
    assert result.key == "acme|"
    assert result.created is True
    assert store.applications["acme|"].role is None


def test_role_missing_with_two_roles_and_unknown_targets_unknown():
    store = Store.empty()
    for mid, role in (("a", "Backend Engineer"), ("b", "Data Engineer"), ("c", None)):
        merge.apply(store, extraction(role=role), email(mid, "2026-10-01T10:00:00Z"))
    result = merge.apply(
        store, extraction(role=None, status="offer"), email("d", "2026-10-04T10:00:00Z")
    )
    assert result.key == "acme|"
    assert result.created is False
    assert store.applications["acme|"].status is Status.OFFER


def test_role_missing_new_company_fixture():
    store = Store.empty()
    result = merge.apply(store, *pair("role_missing_initech"))
    assert result.key == "initech|"
    assert store.applications["initech|"].role is None


# --- company spelling -------------------------------------------------------------------------


def test_company_variants_merge_and_display_follows_newest():
    store = Store.empty()
    apply_all(store, pair("confirm_acme_backend"), pair("acme_variant_spelling"))
    assert set(store.applications) == {"acme|backend engineer"}
    assert store.applications["acme|backend engineer"].company == "ACME Corporation"

    merge.apply(store, *pair("delayed_old_email"))  # "Acme", newer than the variant
    assert store.applications["acme|backend engineer"].company == "Acme"

    merge.apply(store, *pair("confirm_acme_backend", company="ACME CORP"))  # older: no change
    assert store.applications["acme|backend engineer"].company == "Acme"


# --- truncation and storage -------------------------------------------------------------------


def test_subject_truncated_to_200():
    store = Store.empty()
    merge.apply(store, extraction(), email("a", "2026-10-01T10:00:00Z", subject="s" * 250))
    assert store.applications["acme|backend engineer"].subject == "s" * 200


def test_new_application_fields():
    store = Store.empty()
    e, m = pair("interview_globex_data")
    merge.apply(store, e, m)
    app = store.applications["globex|data engineer"]
    assert app.company == "Globex"
    assert app.role == "Data Engineer"
    assert app.status is Status.INTERVIEW
    assert app.first_seen == app.last_activity == m.date
    assert app.thread_id == m.thread_id
    assert app.subject == m.subject
    assert app.evidence == e.evidence
    assert app.message_ids == [m.message_id]


def test_apply_rejects_unusable_extraction():
    store = Store.empty()
    with pytest.raises(ValueError):
        merge.apply(store, extraction(status="unknown"), email("a", "2026-10-01T10:00:00Z"))
    assert store.applications == {}


# --- rule 4: badges -----------------------------------------------------------------------------


def run(store, *pairs):
    """Apply `pairs` as one sync run and return its (added, updated) badge lists."""
    tracker = merge.BadgeTracker.begin(store)
    for e, m in pairs:
        tracker.record(merge.apply(store, e, m))
    return tracker.badges(store)


def test_created_in_this_run_is_added():
    store = Store.empty()
    assert run(store, pair("confirm_acme_backend")) == (["acme|backend engineer"], [])


def test_created_then_changed_in_same_run_is_only_added():
    store = Store.empty()
    badges = run(store, pair("confirm_acme_backend"), pair("reject_acme_backend"))
    assert badges == (["acme|backend engineer"], [])


def test_status_change_in_later_run_is_updated():
    store = Store.empty()
    run(store, pair("confirm_acme_backend"))
    assert run(store, pair("reject_acme_backend")) == ([], ["acme|backend engineer"])


def test_last_activity_change_alone_is_updated():
    store = Store.empty()
    merge.apply(store, extraction(status="applied"), email("a", "2026-10-01T10:00:00Z"))
    badges = run(store, (extraction(status="applied"), email("b", "2026-10-02T10:00:00Z")))
    assert badges == ([], ["acme|backend engineer"])


def test_role_filled_by_rekey_is_updated_under_new_key():
    store = Store.empty()
    merge.apply(store, extraction(role=None), email("a", "2026-10-01T10:00:00Z"))
    badges = run(store, (extraction(), email("b", "2026-10-02T10:00:00Z")))
    assert badges == ([], ["acme|backend engineer"])


def test_created_then_rekeyed_in_same_run_is_added_under_new_key():
    store = Store.empty()
    badges = run(
        store,
        (extraction(role=None), email("a", "2026-10-01T10:00:00Z")),
        (extraction(), email("b", "2026-10-02T10:00:00Z")),
    )
    assert badges == (["acme|backend engineer"], [])


def test_delayed_older_email_gives_no_badge():
    store = Store.empty()
    run(store, pair("confirm_acme_backend"), pair("reject_acme_backend"))
    before = store.applications["acme|backend engineer"].model_copy(deep=True)

    assert run(store, pair("delayed_old_email")) == ([], [])
    app = store.applications["acme|backend engineer"]
    assert app.status is before.status
    assert app.last_activity == before.last_activity
    assert app.first_seen == before.first_seen
    assert app.message_ids == [*before.message_ids, "msg-acme-003"]


def test_first_seen_only_change_gives_no_badge():
    store = Store.empty()
    run(store, pair("confirm_acme_backend"))
    older = (extraction(status="applied"), email("early", "2026-09-01T10:00:00Z"))

    assert run(store, older) == ([], [])
    assert store.applications["acme|backend engineer"].first_seen == datetime(
        2026, 9, 1, 10, 0, tzinfo=UTC
    )


def test_badge_lists_are_sorted():
    store = Store.empty()
    badges = run(
        store,
        (extraction(company="Zeta"), email("z", "2026-10-02T10:00:00Z")),
        (extraction(company="Acme"), email("a", "2026-10-01T10:00:00Z")),
    )
    assert badges == (["acme|backend engineer", "zeta|backend engineer"], [])


def test_badges_with_no_emails_are_empty():
    store = Store.empty()
    run(store, pair("confirm_acme_backend"))
    assert run(store) == ([], [])
