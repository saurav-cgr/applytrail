"""OAuth sign-in and token loading (contracts/cli.md `applytrail-auth`). No network, no browser."""

import json
import stat

import pytest
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials

from applytrail import gmail_auth
from applytrail.config import Settings
from applytrail.errors import AuthRequired, NetworkUnavailable

READONLY = "https://www.googleapis.com/auth/gmail.readonly"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no stray .env from the working directory
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
    return Settings.from_env()


def token_info(scopes=(READONLY,), expiry="2099-01-01T00:00:00Z", refresh_token="refresh-1"):
    info = {
        "token": "access-1",
        "refresh_token": refresh_token,
        "client_id": "client.apps.example",
        "client_secret": "secret",
        "scopes": list(scopes),
        "expiry": expiry,
    }
    return {k: v for k, v in info.items() if v is not None}


def write_token(settings, info):
    settings.home.mkdir(parents=True, exist_ok=True)
    settings.token_path.write_text(json.dumps(info), encoding="utf-8")


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


class FakeCreds:
    def to_json(self):
        return json.dumps(token_info())


class FakeFlow:
    calls: list = []
    error: BaseException | None = None

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        cls.calls.append(("from_client_secrets_file", path, scopes))
        return cls()

    def run_local_server(self, **kwargs):
        FakeFlow.calls.append(("run_local_server", kwargs))
        if FakeFlow.error is not None:
            raise FakeFlow.error
        return FakeCreds()


class NoBrowser:
    def __getattr__(self, name):
        raise AssertionError("load_credentials must never start an OAuth flow")


@pytest.fixture
def flow(monkeypatch):
    FakeFlow.calls = []
    FakeFlow.error = None
    monkeypatch.setattr(gmail_auth, "InstalledAppFlow", FakeFlow)
    return FakeFlow


def test_only_readonly_scope():
    assert gmail_auth.SCOPES == [READONLY]


# --- applytrail-auth --------------------------------------------------------------------------


def test_missing_credentials_file(settings, flow, capsys):
    assert gmail_auth.main() == 2
    err = capsys.readouterr().err.strip()
    assert err == f"Missing {settings.credentials_path}. See README: Set up Google OAuth."
    assert flow.calls == []


def test_successful_sign_in_writes_private_token(settings, flow, capsys):
    settings.home.mkdir(parents=True)
    settings.credentials_path.write_text("{}", encoding="utf-8")

    assert gmail_auth.main() == 0

    assert flow.calls[0] == (
        "from_client_secrets_file",
        str(settings.credentials_path),
        [READONLY],
    )
    assert flow.calls[1] == ("run_local_server", {"port": 0})
    assert json.loads(settings.token_path.read_text(encoding="utf-8")) == token_info()
    assert mode(settings.token_path) == 0o600
    assert mode(settings.home) == 0o700
    assert capsys.readouterr().out.strip() == "Gmail read-only access granted. Run applytrail."


def test_existing_world_readable_token_is_replaced_with_private_one(settings, flow):
    settings.home.mkdir(parents=True)
    settings.credentials_path.write_text("{}", encoding="utf-8")
    settings.token_path.write_text("old", encoding="utf-8")
    settings.token_path.chmod(0o644)

    assert gmail_auth.main() == 0
    assert mode(settings.token_path) == 0o600
    assert settings.token_path.read_text(encoding="utf-8") != "old"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ValueError("access_denied"), "access_denied"),
        (KeyboardInterrupt(), "cancelled"),
        (OSError(), "OSError"),
    ],
    ids=["denied", "ctrl-c", "no-message"],
)
def test_failed_sign_in(settings, flow, capsys, error, reason):
    settings.home.mkdir(parents=True)
    settings.credentials_path.write_text("{}", encoding="utf-8")
    flow.error = error

    assert gmail_auth.main() == 1
    assert capsys.readouterr().err.strip() == f"Sign-in did not complete: {reason}"
    assert not settings.token_path.exists()


# --- load_credentials -------------------------------------------------------------------------


@pytest.fixture
def no_browser(monkeypatch):
    monkeypatch.setattr(gmail_auth, "InstalledAppFlow", NoBrowser())


def test_load_valid_token(settings, no_browser):
    write_token(settings, token_info())
    creds = gmail_auth.load_credentials(settings)
    assert isinstance(creds, Credentials)
    assert creds.valid
    assert creds.token == "access-1"


def test_missing_token(settings, no_browser):
    with pytest.raises(AuthRequired):
        gmail_auth.load_credentials(settings)


@pytest.mark.parametrize(
    "content",
    ["{not json", json.dumps({"token": "x"}), json.dumps(["list"])],
    ids=["invalid-json", "missing-fields", "not-an-object"],
)
def test_invalid_token(settings, no_browser, content):
    settings.home.mkdir(parents=True)
    settings.token_path.write_text(content, encoding="utf-8")
    with pytest.raises(AuthRequired):
        gmail_auth.load_credentials(settings)


@pytest.mark.parametrize(
    "scopes",
    [(), ("https://www.googleapis.com/auth/gmail.metadata",)],
    ids=["no-scopes", "other-scope"],
)
def test_token_without_readonly_scope(settings, no_browser, scopes):
    write_token(settings, token_info(scopes=scopes))
    with pytest.raises(AuthRequired):
        gmail_auth.load_credentials(settings)


def test_expired_token_is_refreshed_and_rewritten_private(settings, no_browser, monkeypatch):
    write_token(settings, token_info(expiry="2020-01-01T00:00:00Z"))
    settings.token_path.chmod(0o644)
    refreshed = []

    def fake_refresh(self, request):
        refreshed.append(request)
        self.token = "access-2"
        self.expiry = None

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)

    creds = gmail_auth.load_credentials(settings)

    assert len(refreshed) == 1
    assert creds.token == "access-2"
    saved = json.loads(settings.token_path.read_text(encoding="utf-8"))
    assert saved["token"] == "access-2"
    assert saved["refresh_token"] == "refresh-1"
    assert mode(settings.token_path) == 0o600


def test_expired_token_without_refresh_token(settings, no_browser, monkeypatch):
    info = token_info(expiry="2020-01-01T00:00:00Z")
    write_token(settings, info)
    monkeypatch.setattr(
        Credentials, "refresh", lambda self, request: pytest.fail("must not refresh")
    )
    monkeypatch.setattr(Credentials, "refresh_token", property(lambda self: None))
    with pytest.raises(AuthRequired):
        gmail_auth.load_credentials(settings)


def test_refresh_rejected(settings, no_browser, monkeypatch):
    write_token(settings, token_info(expiry="2020-01-01T00:00:00Z"))
    original = settings.token_path.read_bytes()

    def revoked(self, request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr(Credentials, "refresh", revoked)
    with pytest.raises(AuthRequired):
        gmail_auth.load_credentials(settings)
    assert settings.token_path.read_bytes() == original


def test_refresh_network_failure_is_not_an_auth_problem(settings, no_browser, monkeypatch):
    write_token(settings, token_info(expiry="2020-01-01T00:00:00Z"))

    def offline(self, request):
        raise TransportError("Failed to establish a new connection")

    monkeypatch.setattr(Credentials, "refresh", offline)
    with pytest.raises(NetworkUnavailable):
        gmail_auth.load_credentials(settings)
