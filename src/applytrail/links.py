"""Gmail web addresses for saved threads (research R8)."""

from urllib.parse import quote

GMAIL_THREAD_URL_TEMPLATE = "https://mail.google.com/mail/u/{account}/#all/{thread_id}"


def thread_url(thread_id: str, mailbox: str | None = None) -> str:
    """Address of one thread. Without a mailbox, Gmail's first signed-in account (`u/0`)."""
    return GMAIL_THREAD_URL_TEMPLATE.format(account="0", thread_id=quote(thread_id, safe=""))
