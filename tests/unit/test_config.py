"""Settings from environment variables and the host helpers."""

import stat
from pathlib import Path

import pytest

from applytrail.config import Settings, ensure_home, is_loopback_host

ENV = ("APPLYTRAIL_HOME", "APPLYTRAIL_MODEL", "OLLAMA_HOST", "APPLYTRAIL_DEBUG")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    s = Settings.from_env()
    assert s.home == Path("~/.applytrail").expanduser()
    assert s.model == "qwen3:4b"
    assert s.ollama_host == "http://127.0.0.1:11434"
    assert s.debug is False


def test_derived_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path))
    s = Settings.from_env()
    assert s.store_path == tmp_path / "applications.json"
    assert s.token_path == tmp_path / "token.json"
    assert s.credentials_path == tmp_path / "credentials.json"
    assert s.debug_log_path == tmp_path / "debug.log"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("localhost:11434", "http://localhost:11434"),
        ("http://10.0.0.5:11434/", "http://10.0.0.5:11434"),
        ("https://ollama.example", "https://ollama.example"),
    ],
)
def test_ollama_host_normalized(monkeypatch, raw, expected):
    monkeypatch.setenv("OLLAMA_HOST", raw)
    assert Settings.from_env().ollama_host == expected


def test_debug_only_when_exactly_1(monkeypatch):
    monkeypatch.setenv("APPLYTRAIL_DEBUG", "true")
    assert Settings.from_env().debug is False
    monkeypatch.setenv("APPLYTRAIL_DEBUG", "1")
    assert Settings.from_env().debug is True


@pytest.mark.parametrize(
    ("url", "loopback"),
    [
        ("http://localhost:11434", True),
        ("http://127.0.0.1:11434", True),
        ("http://127.8.9.10", True),
        ("http://[::1]:11434", True),
        ("http://10.0.0.5:11434", False),
        ("http://ollama.example", False),
        ("http://localhost.attacker.example", False),
    ],
)
def test_is_loopback_host(url, loopback):
    assert is_loopback_host(url) is loopback


def test_ensure_home_mode_0700(monkeypatch, tmp_path):
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "data"))
    home = ensure_home(Settings.from_env())
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
