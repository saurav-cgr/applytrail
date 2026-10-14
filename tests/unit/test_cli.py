"""`applytrail` default command with fakes: no Gmail, no Ollama (T032, contracts/cli.md)."""

import json
from datetime import UTC, datetime

import pytest

from applytrail import __version__, cli, extractor, mcp_client, render, store, sync
from applytrail.config import Settings
from applytrail.errors import (
    AuthRequired,
    GmailError,
    GmailRateLimited,
    ModelMissing,
    NetworkUnavailable,
    ProviderNotRunning,
    ProviderUnavailable,
)
from applytrail.models import Application, ProcessedEmail, Store
from tests.fakes import FakeExtractor, FakeMcpClient, load_fixtures

WHEN = datetime(2026, 10, 12, 14, 3, tzinfo=UTC)


class Harness:
    """Patches `GmailMcp`, `OllamaExtractor` and `run_sync`; records the order of events."""

    def __init__(self, monkeypatch, tmp_path):
        self.events: list[str] = []
        self.gmail_settings: list[Settings] = []
        self.extractor_settings: list[Settings] = []
        self.ready_error = None
        self.sync_behaviour = None  # callable(store, on_progress) run inside the fake sync
        self.fixtures = load_fixtures()
        harness = self

        class FakeGmailMcp:
            def __init__(self, settings):
                harness.events.append("gmail")
                harness.gmail_settings.append(settings)

            def __enter__(self):
                return FakeMcpClient(harness.fixtures)

            def __exit__(self, *exc_info):
                return None

        def make_extractor(settings):
            harness.extractor_settings.append(settings)
            fake = FakeExtractor(harness.fixtures, ready_error=harness.ready_error)
            real_check = fake.check_ready

            def check_ready():
                harness.events.append("check_ready")
                real_check()

            fake.check_ready = check_ready
            return fake

        real_run_sync = sync.run_sync

        def fake_run_sync(data, mcp, extract, settings, now, on_progress=None):
            harness.events.append("sync")
            if harness.sync_behaviour is None:
                return real_run_sync(data, mcp, extract, settings, now, on_progress)
            return harness.sync_behaviour(data, on_progress)

        real_save = store.save

        def spy_save(data, path):
            harness.events.append("save")
            real_save(data, path)

        real_render = render.render_table

        def spy_render(data, console):
            harness.events.append("table")
            real_render(data, console)

        monkeypatch.setattr(mcp_client, "GmailMcp", FakeGmailMcp)
        monkeypatch.setattr(extractor, "OllamaExtractor", make_extractor)
        monkeypatch.setattr(sync, "run_sync", fake_run_sync)
        monkeypatch.setattr(store, "save", spy_save)
        monkeypatch.setattr(render, "render_table", spy_render)

        monkeypatch.chdir(tmp_path)  # no stray .env from the working directory
        monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
        monkeypatch.delenv("APPLYTRAIL_DEBUG", raising=False)
        self.settings = Settings.from_env()


@pytest.fixture
def harness(monkeypatch, tmp_path):
    return Harness(monkeypatch, tmp_path)


def merge_one_then_raise(error):
    """A sync that merges one application, then fails."""

    def behaviour(data, on_progress):
        data.applications["globex|data engineer"] = Application(
            key="globex|data engineer",
            company="Globex",
            role="Data Engineer",
            status="interview",
            last_activity=WHEN,
            first_seen=WHEN,
            thread_id="thr-globex-001",
            subject="Interview invitation",
            evidence="We'd like to invite you",
            message_ids=["msg-globex-001"],
        )
        data.processed["msg-globex-001"] = ProcessedEmail(
            message_id="msg-globex-001",
            date=WHEN,
            outcome="applied",
            application_key="globex|data engineer",
        )
        raise error

    return behaviour


def raise_error(error):
    def behaviour(data, on_progress):
        raise error

    return behaviour


def saved_store(settings) -> Store:
    return store.load(settings.store_path)


def write_existing_store(settings) -> bytes:
    settings.home.mkdir(parents=True, exist_ok=True)
    data = Store.empty().model_dump(mode="json")
    raw = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    settings.store_path.write_bytes(raw)
    return raw


def assert_one_line(err: str, message: str):
    assert err == message + "\n"
    assert "Traceback" not in err


# --- Success ---------------------------------------------------------------------------------


def test_success_prints_table_and_summary(harness, capsys):
    code = cli.main([])

    out, err = capsys.readouterr()
    assert code == 0
    assert "Acme Inc." in out
    assert "Read 10 emails · 4 new · 0 updated · 3 ignored · 0 skipped" in out
    assert "Traceback" not in err
    assert len(saved_store(harness.settings).applications) == 4
    assert harness.events.index("check_ready") < harness.events.index("gmail")


def test_success_with_no_applications_prints_message(harness, capsys):
    harness.fixtures = load_fixtures("newsletter")

    assert cli.main([]) == 0
    out, _ = capsys.readouterr()
    assert "No job applications found yet." in out
    assert "Read 1 emails · 0 new · 0 updated · 1 ignored · 0 skipped" in out


def test_version(harness, capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


# --- Preflight ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error", [ProviderNotRunning("http://127.0.0.1:11434"), ModelMissing("qwen3:4b")]
)
def test_preflight_failure_exits_2_before_gmail(harness, capsys, error):
    raw = write_existing_store(harness.settings)
    harness.ready_error = error

    code = cli.main([])

    _, err = capsys.readouterr()
    assert code == 2
    assert_one_line(err, error.message)
    assert harness.gmail_settings == []
    assert "sync" not in harness.events
    assert "save" not in harness.events
    assert harness.settings.store_path.read_bytes() == raw


# --- Errors during sync --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AuthRequired(), 2),
        (NetworkUnavailable(), 3),
        (ProviderUnavailable("memory", "qwen3:4b"), 4),
        (ProviderUnavailable("unresponsive", "qwen3:4b", pending=8), 4),
        (GmailRateLimited(pending=3), 4),
        (GmailError(500), 1),
    ],
)
def test_app_error_prints_contract_message_and_exit_code(harness, capsys, error, code):
    harness.sync_behaviour = raise_error(error)

    assert cli.main([]) == code
    _, err = capsys.readouterr()
    assert_one_line(err, error.message)


def test_messages_match_the_contract():
    assert ProviderUnavailable("unresponsive", "qwen3:4b", pending=8).message == (
        "Ollama stopped responding. 8 emails pending; progress saved. Run applytrail again."
    )
    assert GmailRateLimited(pending=3).message == (
        "Gmail rate limit reached. 3 emails pending; progress saved. Try again in a few minutes."
    )


@pytest.mark.parametrize(
    "error", [ProviderUnavailable("unresponsive", "qwen3:4b", pending=8), GmailRateLimited(3)]
)
def test_exit_4_saves_then_prints_table_then_message(harness, capsys, error):
    harness.sync_behaviour = merge_one_then_raise(error)

    assert cli.main([]) == 4

    out, err = capsys.readouterr()
    assert harness.events[-2:] == ["save", "table"]
    assert "Globex" in out
    assert_one_line(err, error.message)
    assert "globex|data engineer" in saved_store(harness.settings).applications


def test_network_failure_saves_progress_and_prints_no_table(harness, capsys):
    harness.sync_behaviour = merge_one_then_raise(NetworkUnavailable())

    assert cli.main([]) == 3

    out, err = capsys.readouterr()
    assert out == ""
    assert "table" not in harness.events
    assert_one_line(err, NetworkUnavailable().message)
    assert "msg-globex-001" in saved_store(harness.settings).processed


def test_ctrl_c_saves_progress_and_prints_no_table(harness, capsys):
    harness.sync_behaviour = merge_one_then_raise(KeyboardInterrupt())

    assert cli.main([]) == 130

    out, err = capsys.readouterr()
    assert out == ""
    assert_one_line(err, "Interrupted. Progress saved.")
    assert "msg-globex-001" in saved_store(harness.settings).processed


def test_auth_failure_saves_nothing(harness, capsys):
    raw = write_existing_store(harness.settings)
    harness.sync_behaviour = merge_one_then_raise(AuthRequired())

    assert cli.main([]) == 2
    assert "save" not in harness.events
    assert harness.settings.store_path.read_bytes() == raw


def test_unreadable_store_exits_5_and_is_left_unchanged(harness, capsys):
    harness.settings.home.mkdir(parents=True)
    harness.settings.store_path.write_bytes(b"{corrupt")

    assert cli.main([]) == 5

    _, err = capsys.readouterr()
    assert_one_line(
        err,
        f"Cannot read {harness.settings.store_path}. Move it aside and run applytrail to rebuild.",
    )
    assert harness.settings.store_path.read_bytes() == b"{corrupt"
    assert harness.gmail_settings == []


# --- Environment ---------------------------------------------------------------------------------


def test_dotenv_in_cwd_is_loaded(harness, monkeypatch, tmp_path):
    monkeypatch.setenv("APPLYTRAIL_MODEL", "placeholder")
    monkeypatch.delenv("APPLYTRAIL_MODEL")
    (tmp_path / ".env").write_text("APPLYTRAIL_MODEL=model-from-dotenv\n", encoding="utf-8")

    assert cli.main([]) == 0
    assert harness.extractor_settings[0].model == "model-from-dotenv"


# --- Progress ------------------------------------------------------------------------------------


def progress_then_finish(total):
    def behaviour(data, on_progress):
        for k in range(total + 1):
            on_progress(k, total)
        return data.sync.last_run_counts

    return behaviour


def test_more_than_50_candidates_prints_estimate(harness, capsys):
    harness.sync_behaviour = progress_then_finish(412)

    assert cli.main([]) == 0
    _, err = capsys.readouterr()
    assert (
        "412 emails to process (~20 min with local model). "
        "Ctrl-C is safe; re-running continues where it stopped."
    ) in err


def test_50_candidates_print_no_estimate(harness, capsys):
    harness.sync_behaviour = progress_then_finish(50)

    assert cli.main([]) == 0
    _, err = capsys.readouterr()
    assert "emails to process" not in err


# --- Unexpected errors ---------------------------------------------------------------------------


def test_unexpected_error_prints_one_line(harness, capsys):
    harness.sync_behaviour = raise_error(RuntimeError("Dear candidate, secret body text"))

    assert cli.main([]) == 1

    _, err = capsys.readouterr()
    assert err.count("\n") == 1
    assert "Traceback" not in err
    assert "secret body text" not in err
    assert not harness.settings.debug_log_path.exists()


def test_unexpected_error_with_debug_writes_traceback(harness, capsys, monkeypatch):
    monkeypatch.setenv("APPLYTRAIL_DEBUG", "1")
    harness.sync_behaviour = raise_error(RuntimeError("boom"))

    assert cli.main([]) == 1

    _, err = capsys.readouterr()
    log = harness.settings.debug_log_path
    assert err.count("\n") == 1
    assert str(log) in err
    assert "Traceback" in log.read_text(encoding="utf-8")
    assert (log.stat().st_mode & 0o777) == 0o600


def test_debug_log_omits_exception_messages(harness, capsys, monkeypatch):
    # Exception text can carry email content; the log keeps frames and types only.
    monkeypatch.setenv("APPLYTRAIL_DEBUG", "1")

    # Messages come from variables so the traceback's quoted source lines do not contain them.
    cause_text, error_text = "Dear candidate, cause body text", "Dear candidate, secret body text"

    def behaviour(data, on_progress):
        try:
            raise ValueError(cause_text)
        except ValueError as cause:
            raise RuntimeError(error_text) from cause

    harness.sync_behaviour = behaviour

    assert cli.main([]) == 1

    log = harness.settings.debug_log_path.read_text(encoding="utf-8")
    assert "Traceback" in log
    assert "ValueError" in log
    assert "RuntimeError" in log
    assert "body text" not in log


def test_malformed_dotenv_exits_1_without_traceback(harness, capsys, tmp_path):
    (tmp_path / ".env").write_bytes(b"APPLYTRAIL_MODEL=\xff\n")

    assert cli.main([]) == 1

    _, err = capsys.readouterr()
    assert err.count("\n") == 1
    assert "Traceback" not in err
    assert "UnicodeDecodeError" in err
    assert harness.events == []


def test_ctrl_c_during_preflight_exits_130_without_traceback(harness, capsys):
    harness.ready_error = KeyboardInterrupt()

    assert cli.main([]) == 130

    _, err = capsys.readouterr()
    assert_one_line(err, "Interrupted. Progress saved.")
    assert harness.gmail_settings == []
