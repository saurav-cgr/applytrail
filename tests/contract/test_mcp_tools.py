"""MCP tool contract (contracts/mcp-tools.md) through an in-process `fastmcp.Client`. No Gmail."""

import os
import socket
import sys

import anyio
import httplib2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from googleapiclient.errors import HttpError

from applytrail import gmail_auth, gmail_client, mcp_server
from applytrail.errors import AuthRequired
from tests.fakes import FakeGmailService, b64, load_fixture, raw_message

AFTER = "2026-04-15T00:00:00Z"
FORBIDDEN = ("send", "modify", "label", "trash", "delete", "draft")


@pytest.fixture
def gmail(monkeypatch, tmp_path):
    """Patch auth and the service factory; return a holder whose `.service` tests can replace."""
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))

    class Holder:
        service = FakeGmailService(
            pages=[["m1", "m2"], ["m3"]],
            messages=[
                raw_message("m1", "t1", "Mon, 13 Oct 2026 09:15:00 +0000"),
                raw_message("m2", "t2", "Fri, 10 Oct 2026 08:00:00 +0000"),
                raw_message("m3", "t3", "Sun, 12 Oct 2026 12:00:00 +0000"),
            ],
        )
        settings_seen = []

    def fake_load(settings):
        Holder.settings_seen.append(settings)
        return object()

    monkeypatch.setattr(gmail_auth, "load_credentials", fake_load)
    monkeypatch.setattr(gmail_client, "build_service", lambda creds: Holder.service)
    return Holder


def run(action):
    async def main():
        async with Client(mcp_server.server) as client:
            return await action(client)

    return anyio.run(main)


def call(name, arguments):
    return run(lambda client: client.call_tool(name, arguments, raise_on_error=False))


def tools():
    return {tool.name: tool for tool in run(lambda client: client.list_tools())}


def error_text(result):
    assert result.is_error is True
    return result.content[0].text


# --- listing and schemas ----------------------------------------------------------------------


READ_TOOLS = {"search_job_emails", "get_email", "get_account"}


def test_exactly_three_read_tools_with_descriptions():
    listed = tools()
    assert set(listed) == READ_TOOLS
    assert listed["search_job_emails"].description.startswith(
        "List IDs of likely job-application emails received after a given time, oldest first."
    )
    assert listed["get_email"].description.startswith(
        "Fetch one email's headers and plain-text body, truncated for safe processing."
    )
    assert listed["get_account"].description == (
        "Return the address of the Gmail account this server reads, so links can open the "
        "right mailbox."
    )


def test_no_tool_name_suggests_a_write():
    for name in tools():
        assert not any(word in name for word in FORBIDDEN)


def test_search_input_schema():
    schema = tools()["search_job_emails"].input_schema
    props = schema["properties"]
    assert schema["required"] == ["after"]
    assert props["after"]["format"] == "date-time"
    assert props["max_results"]["minimum"] == 1
    assert props["max_results"]["maximum"] == 500
    assert props["max_results"]["default"] == 500
    assert "page_token" in props


def test_get_email_input_schema():
    schema = tools()["get_email"].input_schema
    props = schema["properties"]
    assert schema["required"] == ["message_id"]
    assert props["max_chars"]["minimum"] == 500
    assert props["max_chars"]["maximum"] == 20000
    assert props["max_chars"]["default"] == 4000


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_job_emails", {"after": AFTER, "max_results": 0}),
        ("search_job_emails", {"after": AFTER, "max_results": 501}),
        ("search_job_emails", {}),
        ("get_email", {"message_id": "m1", "max_chars": 499}),
        ("get_email", {"message_id": "m1", "max_chars": 20001}),
    ],
    ids=["max-results-0", "max-results-501", "no-after", "max-chars-499", "max-chars-20001"],
)
def test_out_of_range_arguments_rejected(gmail, name, arguments):
    assert call(name, arguments).is_error is True


# --- structured output ------------------------------------------------------------------------


def test_search_structured_content(gmail):
    first = call("search_job_emails", {"after": AFTER, "max_results": 2})
    assert first.is_error is False
    content = first.structured_content
    assert set(content) == {"messages", "next_page_token", "query"}
    assert content["messages"] == [
        {"message_id": "m2", "thread_id": "t2", "date": "2026-10-10T08:00:00Z"},
        {"message_id": "m1", "thread_id": "t1", "date": "2026-10-13T09:15:00Z"},
    ]
    assert content["next_page_token"] == "1"
    assert content["query"].startswith("after:1776211200 -in:chats")

    second = call(
        "search_job_emails",
        {"after": AFTER, "max_results": 2, "page_token": content["next_page_token"]},
    )
    assert [m["message_id"] for m in second.structured_content["messages"]] == ["m3"]
    assert second.structured_content["next_page_token"] is None


def test_get_email_structured_content(gmail):
    fixture = load_fixture("html_only_body")
    gmail.service = FakeGmailService(messages=[fixture["gmail_raw"]])
    result = call("get_email", {"message_id": fixture["message_id"]})
    assert result.is_error is False
    assert result.structured_content == {
        "message_id": fixture["message_id"],
        "thread_id": fixture["thread_id"],
        "date": "2026-10-10T10:00:00Z",
        "sender": fixture["sender"],
        "subject": fixture["subject"],
        "body_text": fixture["body_text"],
        "truncated": False,
    }


def test_get_email_truncates_to_max_chars(gmail):
    payload = {"mimeType": "text/plain", "body": {"data": b64("word " * 300)}}
    gmail.service = FakeGmailService(messages=[raw_message(payload=payload)])
    result = call("get_email", {"message_id": "m1", "max_chars": 500})
    assert len(result.structured_content["body_text"]) == 500
    assert result.structured_content["truncated"] is True


def test_credentials_loaded_on_each_call(gmail):
    call("search_job_emails", {"after": AFTER})
    call("get_email", {"message_id": "m1"})
    assert len(gmail.settings_seen) == 2
    assert gmail.settings_seen[0].home.name == "home"


# --- errors -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "arguments"),
    [("search_job_emails", {"after": AFTER}), ("get_email", {"message_id": "m1"})],
    ids=["search", "get_email"],
)
def test_auth_required(gmail, monkeypatch, name, arguments):
    def missing(settings):
        raise AuthRequired()

    monkeypatch.setattr(gmail_auth, "load_credentials", missing)
    assert error_text(call(name, arguments)) == (
        "AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth."
    )


@pytest.mark.parametrize(
    ("error", "prefix"),
    [
        (socket.gaierror("no route"), "NETWORK:"),
        (HttpError(httplib2.Response({"status": 429}), b"{}"), "RATE_LIMITED:"),
        (HttpError(httplib2.Response({"status": 503}), b"{}"), "GMAIL_ERROR:"),
    ],
    ids=["network", "rate-limited", "gmail-error"],
)
@pytest.mark.parametrize(
    ("name", "arguments"),
    [("search_job_emails", {"after": AFTER}), ("get_email", {"message_id": "m1"})],
    ids=["search", "get_email"],
)
def test_gmail_failures_are_prefixed(gmail, error, prefix, name, arguments):
    gmail.service = FakeGmailService(pages=[["m1"]], messages=[raw_message()], error=error)
    assert error_text(call(name, arguments)).startswith(prefix)


def test_gmail_error_text_carries_status(gmail):
    error = HttpError(httplib2.Response({"status": 503}), b"{}")
    gmail.service = FakeGmailService(messages=[raw_message()], error=error)
    assert error_text(call("get_email", {"message_id": "m1"})) == "GMAIL_ERROR: HTTP 503"


def test_unexpected_failure_is_masked(gmail):
    gmail.service = FakeGmailService(messages=[])  # unknown ID: the server crashes internally
    text = error_text(call("get_email", {"message_id": "missing-id"}))
    assert text == "Error calling tool 'get_email'"
    assert "NoneType" not in text


def test_server_never_prints_to_stdout(gmail, capfd):
    call("search_job_emails", {"after": AFTER})
    call("get_email", {"message_id": "missing-id"})
    assert capfd.readouterr().out == ""


def test_output_schemas_are_advertised():
    listed = tools()
    assert set(listed["search_job_emails"].output_schema["properties"]) == {
        "messages",
        "next_page_token",
        "query",
    }
    assert "truncated" in listed["get_email"].output_schema["properties"]


def test_stdio_server_without_token_reports_auth_required(tmp_path):
    """Spawn the real `python -m applytrail.mcp_server` over stdio. No token, so no Gmail call."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "applytrail.mcp_server"],
        env={**os.environ, "APPLYTRAIL_HOME": str(tmp_path / "empty-home")},
    )

    async def main():
        async with Client(transport) as client:
            names = {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                "search_job_emails", {"after": AFTER}, raise_on_error=False
            )
            return names, result

    names, result = anyio.run(main)
    assert names == READ_TOOLS
    assert error_text(result) == (
        "AUTH_REQUIRED: Gmail access not set up or expired. Run applytrail-auth."
    )


# --- get_account (002 US3) --------------------------------------------------------------------


def test_get_account_takes_no_arguments():
    schema = tools()["get_account"].input_schema
    assert schema.get("properties", {}) == {}
    assert schema.get("required", []) == []


def test_get_account_structured_content(gmail):
    result = call("get_account", {})
    assert result.is_error is False
    assert result.structured_content == {"email_address": "me@example.com"}
    assert gmail.service.calls == [("getProfile", {"userId": "me"})]


def test_get_account_without_auth_is_auth_required(gmail, monkeypatch):
    def missing(settings):
        raise AuthRequired()

    monkeypatch.setattr(gmail_auth, "load_credentials", missing)
    assert error_text(call("get_account", {})).startswith("AUTH_REQUIRED:")


def test_get_account_never_logs_the_address(gmail, caplog, capfd):
    gmail.service = FakeGmailService(email="secret+jobs@example.com")
    with caplog.at_level("DEBUG"):
        call("get_account", {})
        gmail.service = FakeGmailService(
            email="secret+jobs@example.com",
            profile_error=HttpError(httplib2.Response({"status": 503}), b"{}"),
        )
        call("get_account", {})
    captured = capfd.readouterr()
    assert "secret" not in caplog.text
    assert "secret" not in captured.out + captured.err


def test_get_account_rejected_address_is_never_logged(gmail, caplog, capfd):
    # V-009: FastMCP logs tool exceptions with their traceback; a validation error carried the
    # rejected address in its input_value.
    gmail.service = FakeGmailService(email="secret+jobs@example.com\n")
    with caplog.at_level("DEBUG"):
        result = call("get_account", {})
    captured = capfd.readouterr()
    assert error_text(result) == "GMAIL_ERROR: HTTP unknown"
    assert "secret" not in caplog.text
    assert "secret" not in captured.out + captured.err
