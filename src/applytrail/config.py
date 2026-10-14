"""Settings from environment variables (contracts/cli.md "Environment variables")."""

import ipaddress
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

FIRST_RUN_LOOKBACK_DAYS = 182
OVERLAP = timedelta(hours=1)
SAVE_EVERY = 10
BODY_MAX_CHARS = 4000

DEFAULT_HOME = "~/.applytrail"
DEFAULT_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


def _normalize_host(raw: str) -> str:
    host = raw.strip()
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/")


@dataclass(frozen=True)
class Settings:
    home: Path
    model: str
    ollama_host: str
    debug: bool

    @classmethod
    def from_env(cls) -> "Settings":
        home = os.environ.get("APPLYTRAIL_HOME") or DEFAULT_HOME
        return cls(
            home=Path(home).expanduser(),
            model=os.environ.get("APPLYTRAIL_MODEL") or DEFAULT_MODEL,
            ollama_host=_normalize_host(os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST),
            debug=os.environ.get("APPLYTRAIL_DEBUG") == "1",
        )

    @property
    def store_path(self) -> Path:
        return self.home / "applications.json"

    @property
    def token_path(self) -> Path:
        return self.home / "token.json"

    @property
    def credentials_path(self) -> Path:
        return self.home / "credentials.json"

    @property
    def debug_log_path(self) -> Path:
        return self.home / "debug.log"


def is_loopback_host(url: str) -> bool:
    """True for localhost, 127.0.0.0/8 and ::1."""
    hostname = urlsplit(_normalize_host(url)).hostname or ""
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def ensure_home(settings: Settings) -> Path:
    """Create the data folder with mode 0700 and return it."""
    settings.home.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(settings.home, 0o700)
    return settings.home
