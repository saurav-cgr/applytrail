"""Gmail thread addresses (T005, research R8)."""

from applytrail.links import thread_url


def test_thread_url_defaults_to_first_signed_in_account():
    assert thread_url("18c2f0a1b2") == "https://mail.google.com/mail/u/0/#all/18c2f0a1b2"


def test_thread_id_is_percent_encoded():
    url = thread_url("a/b#c")
    assert url == "https://mail.google.com/mail/u/0/#all/a%2Fb%23c"
    assert url.count("#") == 1
