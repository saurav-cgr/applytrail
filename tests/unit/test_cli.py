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


# --- --offline (US3) ------------------------------------------------------------------------------


@pytest.fixture
def offline(harness, monkeypatch):
    """No Gmail client, no model, no socket: any attempt fails the test."""
    import socket
    import time

    def forbidden(*args, **kwargs):
        raise AssertionError("--offline must not touch the network")

    monkeypatch.setattr(mcp_client, "GmailMcp", forbidden)
    monkeypatch.setattr(extractor, "OllamaExtractor", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield harness
    monkeypatch.undo()
    time.tzset()


def write_store(settings, data: Store) -> bytes:
    settings.home.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    settings.store_path.write_bytes(raw)
    return raw


def synced_store(**sync_fields) -> Store:
    when = datetime(2026, 10, 12, 14, 3, tzinfo=UTC)
    acme = Application(
        key="acme|backend engineer",
        company="Acme Inc.",
        role="Backend Engineer",
        status="rejected",
        last_activity=when,
        first_seen=when,
        thread_id="thr-acme",
        subject="Your application",
        evidence="not moving forward",
        message_ids=["msg-acme-004"],
    )
    globex = acme.model_copy(
        update={"key": "globex|data analyst", "company": "Globex", "role": "Data Analyst"}
    )
    data = Store.empty()
    data.applications = {acme.key: acme, globex.key: globex}
    data.sync.added = [globex.key]
    data.sync.updated = [acme.key]
    data.sync.last_sync_at = datetime(2026, 10, 14, 8, 2, 30, tzinfo=UTC)
    data.sync.checkpoint = when
    data.sync.last_sync_complete = True
    data.sync.stop_reason = "complete"
    for name, value in sync_fields.items():
        setattr(data.sync, name, value)
    return data


def test_offline_prints_stored_table_and_last_sync(offline, capsys):
    path = offline.settings.store_path
    raw = write_store(offline.settings, synced_store())
    mtime = path.stat().st_mtime_ns

    assert cli.main(["--offline"]) == 0

    out, err = capsys.readouterr()
    assert err == ""
    assert "NEW" in out and "Globex" in out
    assert "UPD" in out and "Acme Inc." in out
    assert out.rstrip().splitlines()[-1] == "Last sync: 2026-10-14 08:02 (complete)"
    assert path.read_bytes() == raw
    assert path.stat().st_mtime_ns == mtime
    assert "save" not in offline.events


def test_offline_incomplete_sync_shows_pending(offline, capsys):
    data = synced_store(last_sync_complete=False, stop_reason="provider_unavailable", pending=230)
    write_store(offline.settings, data)

    assert cli.main(["--offline"]) == 0

    out, _ = capsys.readouterr()
    assert out.rstrip().splitlines()[-1] == (
        "Last sync: 2026-10-14 08:02 (incomplete — 230 emails pending; run applytrail to continue)"
    )


def test_offline_incomplete_sync_with_nothing_pending(offline, capsys):
    write_store(offline.settings, synced_store(last_sync_complete=False, stop_reason="network"))

    assert cli.main(["--offline"]) == 0

    out, _ = capsys.readouterr()
    assert out.rstrip().splitlines()[-1] == (
        "Last sync: 2026-10-14 08:02 (incomplete; run applytrail to continue)"
    )


def test_offline_missing_store_says_no_data(offline, capsys):
    assert cli.main(["--offline"]) == 0

    out, err = capsys.readouterr()
    assert out == ""
    assert_one_line(err, "No data yet. Run applytrail to sync.")
    assert not offline.settings.store_path.exists()
    assert not offline.settings.home.exists()


def test_offline_never_synced_empty_store_says_no_data(offline, capsys):
    raw = write_existing_store(offline.settings)

    assert cli.main(["--offline"]) == 0

    out, err = capsys.readouterr()
    assert out == ""
    assert_one_line(err, "No data yet. Run applytrail to sync.")
    assert offline.settings.store_path.read_bytes() == raw


def test_offline_synced_store_without_applications_shows_last_sync(offline, capsys):
    data = synced_store()
    data.applications = {}
    data.sync.added = data.sync.updated = []
    write_store(offline.settings, data)

    assert cli.main(["--offline"]) == 0

    out, err = capsys.readouterr()
    assert err == ""
    assert out.splitlines() == [
        "No job applications found yet.",
        "Last sync: 2026-10-14 08:02 (complete)",
    ]


def test_offline_unreadable_store_exits_5(offline, capsys):
    offline.settings.home.mkdir(parents=True)
    offline.settings.store_path.write_text("{not json", encoding="utf-8")

    assert cli.main(["--offline"]) == 5

    _, err = capsys.readouterr()
    assert_one_line(
        err,
        f"Cannot read {offline.settings.store_path}. Move it aside and run applytrail to rebuild.",
    )
    assert offline.settings.store_path.read_text(encoding="utf-8") == "{not json"


def test_offline_imports_no_network_module(tmp_path):
    # A fresh interpreter, because this test process has already imported every module.
    import os
    import subprocess
    import sys

    script = (
        "import sys\n"
        "from applytrail import cli\n"
        "assert cli.main(['--offline']) == 0\n"
        "loaded = [m for m in ('applytrail.mcp_client', 'applytrail.extractor', "
        "'applytrail.sync', 'mcp', 'googleapiclient') if m in sys.modules]\n"
        "print(loaded)\n"
    )
    env = {**os.environ, "APPLYTRAIL_HOME": str(tmp_path / "home")}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "[]\n"


# --- check (US1, T015, contracts/cli.md `check`) -----------------------------------------------


def copy_lookup_store(settings) -> bytes:
    import shutil
    from pathlib import Path

    settings.home.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(__file__).parents[1] / "fixtures" / "store_lookup.json", settings.store_path)
    return settings.store_path.read_bytes()


def test_check_found_exits_0_and_lists_both_rows(offline, capsys):
    raw = copy_lookup_store(offline.settings)

    assert cli.main(["check", "acme"]) == 0

    out, err = capsys.readouterr()
    assert err == ""
    assert out.splitlines()[0] == 'Found 2 applications matching "acme":'
    assert "Backend Engineer" in out and "Data Engineer" in out
    assert offline.settings.store_path.read_bytes() == raw


def test_check_joins_arguments_with_spaces(offline, capsys):
    copy_lookup_store(offline.settings)
    assert cli.main(["check", "acme", "corp"]) == 0
    joined, _ = capsys.readouterr()
    assert cli.main(["check", "acme corp"]) == 0
    single, _ = capsys.readouterr()
    assert joined == single
    assert joined.splitlines()[0] == 'Found 2 applications matching "acme corp":'


def test_check_not_found_exits_6_with_lines_on_stdout(offline, capsys):
    raw = copy_lookup_store(offline.settings)

    assert cli.main(["check", "Initech"]) == 6

    out, err = capsys.readouterr()
    assert err == ""
    assert out.splitlines() == [
        'No application found for "Initech".',
        "Last sync: 2026-10-14 08:02 (complete)",
    ]
    assert offline.settings.store_path.read_bytes() == raw


def test_check_typo_suggests_and_exits_6(offline, capsys):
    raw = copy_lookup_store(offline.settings)

    assert cli.main(["check", "Gogle"]) == 6

    out, _ = capsys.readouterr()
    assert "Did you mean: Google (#2)?" in out.splitlines()
    assert offline.settings.store_path.read_bytes() == raw


@pytest.mark.parametrize("name", ["&", "  ", ",."])
def test_check_empty_name_exits_2(offline, capsys, name):
    raw = copy_lookup_store(offline.settings)

    assert cli.main(["check", name]) == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert_one_line(err, "Enter a company name, for example: applytrail check acme")
    assert offline.settings.store_path.read_bytes() == raw


def test_check_missing_store_says_no_data_and_exits_6(offline, capsys):
    assert cli.main(["check", "acme"]) == 6

    out, err = capsys.readouterr()
    assert out == ""
    assert_one_line(err, "No data yet. Run applytrail to sync.")
    assert not offline.settings.home.exists()


def test_check_never_synced_empty_store_says_no_data(offline, capsys):
    raw = write_existing_store(offline.settings)

    assert cli.main(["check", "acme"]) == 6

    _, err = capsys.readouterr()
    assert_one_line(err, "No data yet. Run applytrail to sync.")
    assert offline.settings.store_path.read_bytes() == raw


def test_check_unreadable_store_exits_5(offline, capsys):
    offline.settings.home.mkdir(parents=True)
    offline.settings.store_path.write_text("{not json", encoding="utf-8")

    assert cli.main(["check", "acme"]) == 5

    _, err = capsys.readouterr()
    assert_one_line(
        err,
        f"Cannot read {offline.settings.store_path}. Move it aside and run applytrail to rebuild.",
    )


def test_check_imports_no_network_module(tmp_path):
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    home = tmp_path / "home"
    home.mkdir()
    shutil.copy(Path(__file__).parents[1] / "fixtures" / "store_lookup.json", home)
    (home / "store_lookup.json").rename(home / "applications.json")
    script = (
        "import sys\n"
        "from applytrail import cli\n"
        "assert cli.main(['check', 'acme']) == 0\n"
        "loaded = [m for m in ('applytrail.mcp_client', 'applytrail.extractor', "
        "'applytrail.sync', 'mcp', 'googleapiclient') if m in sys.modules]\n"
        "print(loaded, file=sys.stderr)\n"
    )
    env = {**os.environ, "APPLYTRAIL_HOME": str(home)}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == "[]\n"


def test_no_subcommand_still_syncs(harness, capsys):
    assert cli.main([]) == 0
    assert "sync" in harness.events


def test_check_not_found_with_a_wordless_company_exits_6(offline, capsys):
    # V-003: a stored company that normalizes to no words must not crash suggestions.
    data = synced_store()
    wordless = next(iter(data.applications.values())).model_copy(
        update={"key": "and|engineer", "company": "And", "role": "Engineer"}
    )
    data.applications[wordless.key] = wordless
    raw = write_store(offline.settings, data)

    assert cli.main(["check", "Initech"]) == 6

    out, err = capsys.readouterr()
    assert err == ""
    assert out.splitlines()[0] == 'No application found for "Initech".'
    assert offline.settings.store_path.read_bytes() == raw
