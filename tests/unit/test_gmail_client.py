"""Gmail API wrapper with a fake `service` object; no network (contracts/mcp-tools.md, R4)."""

import socket
from datetime import UTC, datetime

import httplib2
import pytest
from googleapiclient.errors import HttpError

from applytrail import gmail_client
from applytrail.errors import GmailError, GmailRateLimited, NetworkUnavailable
from applytrail.models import EmailMeta, SearchPage
from tests.fakes import FakeGmailService as FakeService
from tests.fakes import b64, load_fixture, raw_message

AFTER = datetime(2026, 4, 15, 0, 0, tzinfo=UTC)


def http_error(status):
    return HttpError(httplib2.Response({"status": status}), b'{"error": "x"}')


# --- search query -----------------------------------------------------------------------------


def test_query_excludes_noise_folders():
    query = gmail_client.build_query(AFTER)
    for part in ("-in:chats", "-in:sent", "-in:drafts", "-category:promotions"):
        assert part in query


def test_query_after_uses_epoch_seconds():
    query = gmail_client.build_query(AFTER)
    assert query.startswith(f"after:{int(AFTER.timestamp())} ")


@pytest.mark.parametrize(
    "domain",
    [
        "greenhouse.io",
        "lever.co",
        "myworkdayjobs.com",
        "ashbyhq.com",
        "smartrecruiters.com",
        "icims.com",
        "workablemail.com",
        "jobvite.com",
        "teamtailor.com",
    ],
)
def test_query_includes_ats_sender_domains(domain):
    assert domain in gmail_client.SEARCH_QUERY_TEMPLATE


def test_query_has_job_term_or_group():
    template = gmail_client.SEARCH_QUERY_TEMPLATE
    assert "{" in template and "}" in template
    for term in ("application", "interview", "applying"):
        assert term in template


# --- search -----------------------------------------------------------------------------------


def test_search_returns_page_sorted_ascending_with_next_token():
    messages = [
        raw_message("m1", "t1", "Mon, 13 Oct 2026 09:15:00 +0000"),
        raw_message("m2", "t2", "Fri, 10 Oct 2026 08:00:00 +0000"),
        raw_message("m3", "t3", "Sun, 12 Oct 2026 12:00:00 +0000"),
    ]
    service = FakeService(pages=[["m1", "m2"], ["m3"]], messages=messages)

    first = gmail_client.search(service, AFTER, max_results=2)
    assert isinstance(first, SearchPage)
    assert [m.message_id for m in first.messages] == ["m2", "m1"]
    assert [m.thread_id for m in first.messages] == ["t2", "t1"]
    assert first.messages[0].date == datetime(2026, 10, 10, 8, 0, tzinfo=UTC)
    assert first.next_page_token == "1"
    assert first.query == gmail_client.build_query(AFTER)

    second = gmail_client.search(service, AFTER, max_results=2, page_token=first.next_page_token)
    assert [m.message_id for m in second.messages] == ["m3"]
    assert second.next_page_token is None


def test_search_passes_query_page_size_and_token():
    service = FakeService(pages=[[], []], messages=[])
    gmail_client.search(service, AFTER, max_results=50, page_token="1")
    name, kwargs = service.calls[0]
    assert name == "list"
    assert kwargs["userId"] == "me"
    assert kwargs["q"] == gmail_client.build_query(AFTER)
    assert kwargs["maxResults"] == 50
    assert kwargs["pageToken"] == "1"


def test_search_fetches_only_metadata_for_dates():
    service = FakeService(pages=[["m1"]], messages=[raw_message("m1")])
    gmail_client.search(service, AFTER)
    gets = [kwargs for name, kwargs in service.calls if name == "get"]
    assert len(gets) == 1
    assert gets[0]["format"] == "metadata"


def test_search_empty_mailbox():
    page = gmail_client.search(FakeService(), AFTER)
    assert page.messages == []
    assert page.next_page_token is None


def test_only_read_methods_are_called():
    messages = [raw_message("m1"), raw_message("m2", "t2")]
    service = FakeService(pages=[["m1"], ["m2"]], messages=messages)
    page = gmail_client.search(service, AFTER)
    gmail_client.search(service, AFTER, page_token=page.next_page_token)
    gmail_client.get_email(service, "m1")
    assert {name for name, _ in service.calls} == {"list", "get"}


# --- get_email --------------------------------------------------------------------------------


def test_get_email_returns_headers_and_plain_body():
    service = FakeService(messages=[raw_message()])
    email = gmail_client.get_email(service, "m1")
    assert isinstance(email, EmailMeta)
    assert email.message_id == "m1"
    assert email.thread_id == "t1"
    assert email.date == datetime(2026, 10, 13, 9, 15, tzinfo=UTC)
    assert email.sender == "Acme Recruiting <no-reply@greenhouse.io>"
    assert email.subject == "Your application to Acme"
    assert email.body_text == "Hi there"
    assert email.truncated is False
    assert service.calls[0][1]["format"] == "full"


def test_get_email_prefers_plain_over_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": b64("<p>From HTML</p>")}},
            {"mimeType": "text/plain", "body": {"data": b64("From plain")}},
        ],
    }
    service = FakeService(messages=[raw_message(payload=payload)])
    assert gmail_client.get_email(service, "m1").body_text == "From plain"


def test_get_email_finds_nested_plain_part():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": b64("Nested")}}],
            },
            {"mimeType": "application/pdf", "filename": "cv.pdf", "body": {"attachmentId": "a"}},
        ],
    }
    service = FakeService(messages=[raw_message(payload=payload)])
    assert gmail_client.get_email(service, "m1").body_text == "Nested"


def test_html_only_fixture_converts_to_text_without_script_or_style():
    fixture = load_fixture("html_only_body")
    service = FakeService(messages=[fixture["gmail_raw"]])
    email = gmail_client.get_email(service, fixture["message_id"])
    assert email.body_text == fixture["body_text"]
    assert "alert" not in email.body_text
    assert "color" not in email.body_text
    assert email.date == datetime(2026, 10, 10, 10, 0, tzinfo=UTC)


def test_html_entities_and_block_tags():
    html = "<div>Hello&nbsp;Alex</div><div>Next&amp;step</div>line<br>break"
    payload = {"mimeType": "text/html", "body": {"data": b64(html)}}
    service = FakeService(messages=[raw_message(payload=payload)])
    assert gmail_client.get_email(service, "m1").body_text == "Hello Alex Next&step line break"


def test_whitespace_collapsed():
    payload = {"mimeType": "text/plain", "body": {"data": b64("  Hi\n\n  Alex,\t\tthanks  \r\n")}}
    service = FakeService(messages=[raw_message(payload=payload)])
    assert gmail_client.get_email(service, "m1").body_text == "Hi Alex, thanks"


def test_body_truncated_to_max_chars():
    payload = {"mimeType": "text/plain", "body": {"data": b64("word " * 300)}}
    service = FakeService(messages=[raw_message(payload=payload)])
    email = gmail_client.get_email(service, "m1", max_chars=500)
    assert len(email.body_text) == 500
    assert email.truncated is True


def test_body_at_limit_is_not_truncated():
    payload = {"mimeType": "text/plain", "body": {"data": b64("x" * 500)}}
    service = FakeService(messages=[raw_message(payload=payload)])
    email = gmail_client.get_email(service, "m1", max_chars=500)
    assert email.truncated is False


def test_missing_body_gives_empty_text():
    payload = {"mimeType": "multipart/mixed", "parts": []}
    service = FakeService(messages=[raw_message(payload=payload)])
    assert gmail_client.get_email(service, "m1").body_text == ""


@pytest.mark.parametrize("date_header", [None, "not a date", "Mon, 13 Oct 2026 09:15:00 -0000"])
def test_unusable_date_header_falls_back_to_internal_date(date_header):
    service = FakeService(
        messages=[raw_message(date_header=date_header, internal_ms="1791626400000")]
    )
    email = gmail_client.get_email(service, "m1")
    assert email.date == datetime(2026, 10, 10, 10, 0, tzinfo=UTC)


def test_date_header_with_offset_converted_to_utc():
    service = FakeService(messages=[raw_message(date_header="Mon, 13 Oct 2026 11:15:00 +0200")])
    assert gmail_client.get_email(service, "m1").date == datetime(2026, 10, 13, 9, 15, tzinfo=UTC)


# --- error mapping ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda s: gmail_client.search(s, AFTER),
        lambda s: gmail_client.get_email(s, "m1"),
    ],
    ids=["search", "get_email"],
)
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (http_error(429), GmailRateLimited),
        (http_error(500), GmailError),
        (http_error(403), GmailError),
        (socket.gaierror("no route"), NetworkUnavailable),
        (ConnectionResetError("reset"), NetworkUnavailable),
        (TimeoutError("timed out"), NetworkUnavailable),
        (httplib2.ServerNotFoundError("Unable to find the server"), NetworkUnavailable),
    ],
    ids=["429", "500", "403", "dns", "reset", "timeout", "server-not-found"],
)
def test_errors_are_mapped(call, error, expected):
    service = FakeService(pages=[["m1"]], messages=[raw_message()], error=error)
    with pytest.raises(expected):
        call(service)


def test_gmail_error_carries_status():
    service = FakeService(messages=[raw_message()], error=http_error(503))
    with pytest.raises(GmailError) as info:
        gmail_client.get_email(service, "m1")
    assert info.value.status == 503
