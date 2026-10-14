"""`GmailMcp`: typed sync wrappers over the MCP protocol. The server runs in-process with a fake
Gmail service, except one test that spawns the real server with no token (no Gmail call)."""

import inspect
import os
import socket
import sys
from datetime import UTC, datetime

import httplib2
import pytest
from fastmcp.client.transports import StdioTransport
from googleapiclient.errors import HttpError

from applytrail import gmail_auth, gmail_client, mcp_server
from applytrail.config import Settings
from applytrail.errors import AuthRequired, GmailError, GmailRateLimited, NetworkUnavailable
from applytrail.mcp_client import GmailMcp
from applytrail.models import EmailMeta, SearchPage
from tests.fakes import FakeGmailService, FakeMcpClient, load_fixture, raw_message

AFTER = datetime(2026, 4, 15, tzinfo=UTC)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
    return Settings.from_env()


@pytest.fixture
def gmail(monkeypatch, settings):
    class Holder:
        service = FakeGmailService(
            pages=[["m1", "m2"], ["m3"]],
            messages=[
                raw_message("m1", "t1", "Mon, 13 Oct 2026 09:15:00 +0000"),
                raw_message("m2", "t2", "Fri, 10 Oct 2026 08:00:00 +0000"),
                raw_message("m3", "t3", "Sun, 12 Oct 2026 12:00:00 +0000"),
            ],
        )

    monkeypatch.setattr(gmail_auth, "load_credentials", lambda s: object())
    monkeypatch.setattr(gmail_client, "build_service", lambda creds: Holder.service)
    return Holder


def in_process(settings):
    return GmailMcp(settings, server=mcp_server.server)


def test_same_method_signatures_as_fake():
    for name in ("search_job_emails", "get_email"):
        real = inspect.signature(getattr(GmailMcp, name))
        fake = inspect.signature(getattr(FakeMcpClient, name))
        assert list(real.parameters) == list(fake.parameters)
        assert real.return_annotation == fake.return_annotation


def test_search_pages_are_typed(settings, gmail):
    with in_process(settings) as mcp:
        first = mcp.search_job_emails(AFTER)
        second = mcp.search_job_emails(AFTER, page_token=first.next_page_token)
    assert isinstance(first, SearchPage)
    assert [m.message_id for m in first.messages + second.messages] == ["m2", "m1", "m3"]
    assert first.messages[0].date == datetime(2026, 10, 10, 8, 0, tzinfo=UTC)
    assert second.next_page_token is None


def test_search_sends_after_as_iso_datetime(settings, gmail):
    with in_process(settings) as mcp:
        page = mcp.search_job_emails(AFTER)
    assert page.query.startswith(f"after:{int(AFTER.timestamp())} ")


def test_get_email_is_typed(settings, gmail):
    fixture = load_fixture("html_only_body")
    gmail.service = FakeGmailService(messages=[fixture["gmail_raw"]])
    with in_process(settings) as mcp:
        email = mcp.get_email(fixture["message_id"])
    assert isinstance(email, EmailMeta)
    assert email.body_text == fixture["body_text"]
    assert email.truncated is False


def test_auth_required(settings, gmail, monkeypatch):
    def missing(s):
        raise AuthRequired()

    monkeypatch.setattr(gmail_auth, "load_credentials", missing)
    with in_process(settings) as mcp, pytest.raises(AuthRequired):
        mcp.search_job_emails(AFTER)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (socket.gaierror("no route"), NetworkUnavailable),
        (HttpError(httplib2.Response({"status": 429}), b"{}"), GmailRateLimited),
        (HttpError(httplib2.Response({"status": 503}), b"{}"), GmailError),
    ],
    ids=["network", "rate-limited", "gmail-error"],
)
def test_tool_errors_map_back(settings, gmail, error, expected):
    gmail.service = FakeGmailService(pages=[["m1"]], messages=[raw_message()], error=error)
    with in_process(settings) as mcp, pytest.raises(expected):
        mcp.get_email("m1")


def test_gmail_error_keeps_status(settings, gmail):
    error = HttpError(httplib2.Response({"status": 503}), b"{}")
    gmail.service = FakeGmailService(messages=[raw_message()], error=error)
    with in_process(settings) as mcp, pytest.raises(GmailError) as info:
        mcp.get_email("m1")
    assert info.value.status == 503


def test_unexpected_server_failure_is_a_gmail_error(settings, gmail):
    gmail.service = FakeGmailService(messages=[])  # unknown ID: the server crashes internally
    with in_process(settings) as mcp, pytest.raises(GmailError):
        mcp.get_email("no-such-id")


def test_spawn_parameters(settings):
    params = GmailMcp(settings).server_parameters()
    assert isinstance(params, StdioTransport)
    assert params.command == sys.executable
    assert params.args == ["-m", "applytrail.mcp_server"]
    assert params.env["APPLYTRAIL_HOME"] == str(settings.home)
    assert params.env["PATH"] == os.environ["PATH"]


def test_real_stdio_server_without_token(settings):
    with GmailMcp(settings) as mcp, pytest.raises(AuthRequired):
        mcp.search_job_emails(AFTER)


def test_calls_outside_context_fail(settings):
    with pytest.raises(RuntimeError):
        GmailMcp(settings).get_email("m1")
