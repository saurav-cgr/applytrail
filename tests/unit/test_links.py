"""Gmail thread addresses and browser launch (T005, T021; research R8, R9)."""

import webbrowser

import pytest

from applytrail import links
from applytrail.links import can_launch_browser, open_in_browser, thread_url


def test_thread_url_defaults_to_first_signed_in_account():
    assert thread_url("18c2f0a1b2") == "https://mail.google.com/mail/u/0/#all/18c2f0a1b2"


def test_thread_id_is_percent_encoded():
    url = thread_url("a/b#c")
    assert url == "https://mail.google.com/mail/u/0/#all/a%2Fb%23c"
    assert url.count("#") == 1


@pytest.mark.parametrize(
    ("environ", "platform", "expected"),
    [
        ({"SSH_CONNECTION": "10.0.0.1 22 10.0.0.2 51000"}, "darwin", False),
        ({"SSH_CONNECTION": "x", "DISPLAY": ":0"}, "linux", False),
        ({}, "linux", False),
        ({"DISPLAY": ":0"}, "linux", True),
        ({"WAYLAND_DISPLAY": "wayland-0"}, "linux", True),
        ({}, "darwin", True),
        ({}, "win32", True),
    ],
)
def test_can_launch_browser(environ, platform, expected):
    assert can_launch_browser(environ, platform) is expected


def test_open_in_browser_opens_a_new_tab(monkeypatch):
    calls = []
    monkeypatch.setattr(
        links.webbrowser, "open", lambda url, new=0: calls.append((url, new)) or True
    )
    assert open_in_browser("https://mail.google.com/mail/u/0/#all/x") is True
    assert calls == [("https://mail.google.com/mail/u/0/#all/x", 2)]


def test_open_in_browser_false_when_no_browser(monkeypatch):
    monkeypatch.setattr(links.webbrowser, "open", lambda url, new=0: False)
    assert open_in_browser("https://example.invalid") is False


def test_open_in_browser_false_when_webbrowser_raises(monkeypatch):
    def boom(url, new=0):
        raise webbrowser.Error("no runnable browser")

    monkeypatch.setattr(links.webbrowser, "open", boom)
    assert open_in_browser("https://example.invalid") is False
