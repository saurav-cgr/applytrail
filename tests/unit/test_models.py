"""Model constraints from data-model.md."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from applytrail.models import (
    AccountInfo,
    Application,
    EmailMeta,
    Extraction,
    MessageRef,
    ProcessedEmail,
    RunCounts,
    SearchPage,
    Status,
    Store,
    SyncState,
)

NOW = datetime(2026, 10, 12, 14, 3, tzinfo=UTC)


def make_extraction(**overrides):
    data = {
        "is_job_application": True,
        "company": "Acme Inc.",
        "role": "Backend Engineer",
        "status": "applied",
        "evidence": "Thank you for applying",
    }
    data.update(overrides)
    return Extraction.model_validate(data)


def make_application(**overrides):
    data = {
        "key": "acme|backend engineer",
        "company": "Acme Inc.",
        "role": "Backend Engineer",
        "status": "interview",
        "last_activity": NOW,
        "first_seen": NOW - timedelta(days=12),
        "thread_id": "t1",
        "subject": "Interview invitation",
        "evidence": "We'd like to invite you",
        "message_ids": ["m1", "m2"],
    }
    data.update(overrides)
    return Application.model_validate(data)


def make_sync(**overrides):
    data = {
        "checkpoint": None,
        "last_sync_at": None,
        "last_sync_complete": False,
        "stop_reason": None,
        "pending": 0,
        "added": [],
        "updated": [],
        "last_run_counts": RunCounts(),
    }
    data.update(overrides)
    return SyncState.model_validate(data)


# Status


def test_status_values_are_exact():
    assert [s.value for s in Status] == [
        "applied",
        "in_review",
        "assessment",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    ]


def test_status_labels():
    assert [s.label for s in Status] == [
        "Applied",
        "In Review",
        "Assessment",
        "Interview",
        "Offer",
        "Rejected",
        "Withdrawn",
    ]


# Extraction


def test_extraction_accepts_unknown_status():
    assert make_extraction(status="unknown").status == "unknown"


def test_extraction_parses_known_status_as_enum():
    assert make_extraction(status="offer").status is Status.OFFER


def test_extraction_rejects_other_status():
    with pytest.raises(ValidationError):
        make_extraction(status="hired")


def test_extraction_evidence_max_200_chars():
    assert len(make_extraction(evidence="x" * 200).evidence) == 200
    with pytest.raises(ValidationError):
        make_extraction(evidence="x" * 201)


def test_extraction_role_trimmed():
    assert make_extraction(role="  Backend Engineer  ").role == "Backend Engineer"


@pytest.mark.parametrize("role", ["", "   ", None])
def test_extraction_empty_role_becomes_none(role):
    assert make_extraction(role=role).role is None


def test_extraction_company_trimmed():
    assert make_extraction(company="  Acme  ").company == "Acme"


def test_extraction_empty_company_is_allowed_but_empty():
    # Empty company is "unusable", decided in sync.py, not a validation error.
    assert make_extraction(company="   ").company == ""


def test_extraction_requires_is_job_application_bool():
    with pytest.raises(ValidationError):
        Extraction.model_validate(
            {"company": "Acme", "role": None, "status": "applied", "evidence": ""}
        )


# Application


def test_application_subject_max_200_chars():
    assert len(make_application(subject="s" * 200).subject) == 200
    with pytest.raises(ValidationError):
        make_application(subject="s" * 201)


def test_application_evidence_max_200_chars():
    with pytest.raises(ValidationError):
        make_application(evidence="e" * 201)


def test_application_role_may_be_null():
    assert make_application(key="acme|", role=None).role is None


# ProcessedEmail


@pytest.mark.parametrize("outcome", ["applied", "ignored", "skipped"])
def test_processed_outcome_values(outcome):
    pe = ProcessedEmail(message_id="m1", date=NOW, outcome=outcome)
    assert pe.outcome == outcome


def test_processed_rejects_other_outcome():
    with pytest.raises(ValidationError):
        ProcessedEmail(message_id="m1", date=NOW, outcome="failed")


@pytest.mark.parametrize("reason", ["invalid_output", "incomplete", None])
def test_processed_reason_values(reason):
    pe = ProcessedEmail(message_id="m1", date=NOW, outcome="skipped", reason=reason)
    assert pe.reason == reason


def test_processed_rejects_other_reason():
    with pytest.raises(ValidationError):
        ProcessedEmail(message_id="m1", date=NOW, outcome="skipped", reason="timeout")


def test_processed_defaults():
    pe = ProcessedEmail(message_id="m1", date=NOW, outcome="ignored")
    assert pe.reason is None
    assert pe.application_key is None


# SyncState


@pytest.mark.parametrize(
    "reason", ["complete", "provider_unavailable", "network", "interrupted", None]
)
def test_sync_stop_reason_values(reason):
    assert make_sync(stop_reason=reason).stop_reason == reason


def test_sync_rejects_other_stop_reason():
    with pytest.raises(ValidationError):
        make_sync(stop_reason="crashed")


def test_sync_pending_is_int():
    assert make_sync(pending=3).pending == 3
    with pytest.raises(ValidationError):
        make_sync(pending="three")


@pytest.mark.parametrize(
    "fields",
    [
        {"stop_reason": "complete", "last_sync_complete": True},
        {"stop_reason": "complete"},
        {"last_sync_complete": True},
    ],
    ids=["both", "stop-reason-only", "flag-only"],
)
def test_sync_complete_has_zero_pending(fields):
    with pytest.raises(ValidationError):
        make_sync(**fields, pending=2)


def test_run_counts_default_zero():
    assert RunCounts().model_dump() == {
        "read": 0,
        "added": 0,
        "updated": 0,
        "ignored": 0,
        "skipped": 0,
    }


# Datetimes


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        make_application(last_activity=datetime(2026, 10, 12, 14, 3))


def test_naive_datetime_rejected_in_processed():
    with pytest.raises(ValidationError):
        ProcessedEmail(message_id="m1", date=datetime(2026, 10, 12), outcome="ignored")


def test_naive_datetime_rejected_in_sync():
    with pytest.raises(ValidationError):
        make_sync(checkpoint=datetime(2026, 10, 12))


def test_naive_datetime_rejected_in_email_meta():
    with pytest.raises(ValidationError):
        EmailMeta(
            message_id="m1",
            thread_id="t1",
            date=datetime(2026, 10, 12),
            sender="a@example.com",
            subject="s",
            body_text="b",
        )


def test_aware_datetime_converted_to_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    app = make_application(last_activity=datetime(2026, 10, 12, 19, 33, tzinfo=ist))
    assert app.last_activity == NOW
    assert app.last_activity.utcoffset() == timedelta(0)


def test_iso_string_with_z_parses_as_utc():
    pe = ProcessedEmail.model_validate(
        {"message_id": "m1", "date": "2026-10-12T14:03:00Z", "outcome": "ignored"}
    )
    assert pe.date == NOW


# Store


def test_store_empty():
    store = Store.empty()
    assert store.schema_version == 1
    assert store.applications == {}
    assert store.processed == {}
    assert store.sync.checkpoint is None
    assert store.sync.stop_reason is None
    assert store.sync.pending == 0


@pytest.mark.parametrize("version", [2, 0, True, 1.0, "1", None])
def test_store_rejects_other_schema_version(version):
    data = Store.empty().model_dump(mode="json")
    data["schema_version"] = version
    with pytest.raises(ValidationError):
        Store.model_validate(data)


def test_store_round_trip_json():
    store = Store.empty()
    store.applications["acme|backend engineer"] = make_application()
    store.processed["m1"] = ProcessedEmail(
        message_id="m1", date=NOW, outcome="applied", application_key="acme|backend engineer"
    )
    again = Store.model_validate(store.model_dump(mode="json"))
    assert again == store


def test_email_meta_truncated_defaults_false():
    email = EmailMeta(
        message_id="m1", thread_id="t1", date=NOW, sender="a@b.example", subject="s", body_text="b"
    )
    assert email.truncated is False


def test_search_page_shape():
    page = SearchPage.model_validate(
        {
            "messages": [{"message_id": "m1", "thread_id": "t1", "date": "2026-10-13T09:15:00Z"}],
            "next_page_token": None,
            "query": "after:1 x",
        }
    )
    assert page.messages[0] == MessageRef(
        message_id="m1", thread_id="t1", date=datetime(2026, 10, 13, 9, 15, tzinfo=UTC)
    )
    assert page.next_page_token is None


def test_message_ref_rejects_naive_date():
    with pytest.raises(ValidationError):
        MessageRef(message_id="m1", thread_id="t1", date=datetime(2026, 10, 13, 9, 15))


# Mailbox (002 US3, data-model.md SyncState.mailbox and AccountInfo)

BAD_MAILBOXES = ["a", "a@b@c", "me @x.com", "me\n@x.com", "me\t@x.com", "noat", "x" * 251 + "@x.co"]


def test_sync_mailbox_defaults_to_none():
    assert SyncState().mailbox is None


@pytest.mark.parametrize("value", ["me+jobs@example.com", "a@b", "x" * 249 + "@x.co"])
def test_mailbox_accepts_valid_addresses(value):
    assert make_sync(mailbox=value).mailbox == value
    assert AccountInfo(email_address=value).email_address == value


@pytest.mark.parametrize("value", BAD_MAILBOXES)
def test_sync_mailbox_rejects_invalid(value):
    with pytest.raises(ValidationError):
        make_sync(mailbox=value)


@pytest.mark.parametrize("value", BAD_MAILBOXES)
def test_account_info_rejects_invalid(value):
    with pytest.raises(ValidationError):
        AccountInfo(email_address=value)


def test_mailbox_255_characters_rejected():
    value = "x" * 249 + "@x.com"
    assert len(value) == 255
    with pytest.raises(ValidationError):
        make_sync(mailbox=value)
