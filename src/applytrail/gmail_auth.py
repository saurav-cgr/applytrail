"""Google OAuth for Gmail read-only access (`applytrail-auth`, contracts/cli.md).

Only `main()` opens a browser. `load_credentials()` runs inside the MCP server and never does.
"""

import json
import sys

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from applytrail.config import Settings, ensure_home
from applytrail.errors import AuthRequired, NetworkUnavailable
from applytrail.store import write_private

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> int:
    load_dotenv()
    settings = Settings.from_env()
    if not settings.credentials_path.exists():
        print(
            f"Missing {settings.credentials_path}. See README: Set up Google OAuth.",
            file=sys.stderr,
        )
        return 2
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(settings.credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)
    except KeyboardInterrupt:
        print("Sign-in did not complete: cancelled", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Sign-in did not complete: {_short_reason(err)}", file=sys.stderr)
        return 1
    ensure_home(settings)
    write_private(settings.token_path, creds.to_json())
    print("Gmail read-only access granted. Run applytrail.")
    return 0


def load_credentials(settings: Settings) -> Credentials:
    """Load the saved token, refreshing it if expired. Raise AuthRequired if unusable."""
    try:
        info = json.loads(settings.token_path.read_text(encoding="utf-8"))
        creds = Credentials.from_authorized_user_info(info)
    except (OSError, ValueError, TypeError, AttributeError) as err:
        raise AuthRequired() from err
    if not creds.has_scopes(SCOPES):
        raise AuthRequired()
    if creds.valid:
        return creds
    if not creds.refresh_token:
        raise AuthRequired()
    try:
        creds.refresh(Request())
    except RefreshError as err:
        raise AuthRequired() from err
    except TransportError as err:
        raise NetworkUnavailable() from err
    write_private(settings.token_path, creds.to_json())
    return creds


def _short_reason(err: BaseException) -> str:
    text = str(err).strip()
    return text.splitlines()[0] if text else type(err).__name__
