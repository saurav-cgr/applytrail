"""Gmail web addresses for saved threads and opening them (research R8, R9)."""

import os
import sys
import webbrowser
from collections.abc import Mapping
from urllib.parse import quote

GMAIL_THREAD_URL_TEMPLATE = "https://mail.google.com/mail/u/{account}/#all/{thread_id}"


def thread_url(thread_id: str, mailbox: str | None = None) -> str:
    """Address of one thread in `mailbox`'s account, or Gmail's first signed-in account
    (`u/0`) when no mailbox is known."""
    account = "0" if mailbox is None else quote(mailbox, safe="@")
    return GMAIL_THREAD_URL_TEMPLATE.format(account=account, thread_id=quote(thread_id, safe=""))


def can_launch_browser(
    environ: Mapping[str, str] = os.environ, platform: str = sys.platform
) -> bool:
    """False over SSH or on Linux without a display, where `webbrowser` would fall back to a
    console browser that takes over the terminal."""
    if environ.get("SSH_CONNECTION"):
        return False
    if platform.startswith("linux"):
        return bool(environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY"))
    return True


def open_in_browser(url: str) -> bool:
    """Open `url` in a new browser tab; False when no browser could be started."""
    try:
        return bool(webbrowser.open(url, new=2))
    except webbrowser.Error:
        return False
