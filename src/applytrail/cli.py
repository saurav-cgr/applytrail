"""`applytrail`: sync new mail, save, print the table (contracts/cli.md).

Expected failures print one line to stderr and exit with their code, never a stack trace
(Principle VII). The table goes to stdout; progress and messages go to stderr.
"""

import argparse
import sys
import traceback
from datetime import UTC, datetime

from dotenv import find_dotenv, load_dotenv
from rich.console import Console

from applytrail import __version__, render, store
from applytrail.config import Settings, ensure_home
from applytrail.errors import AppError, Interrupted

SECONDS_PER_EMAIL = 3
ESTIMATE_THRESHOLD = 50

# Exit codes whose partial progress is saved before exiting (contracts/cli.md).
_SAVE_ON_EXIT = {3, 4}
_TABLE_ON_EXIT = {4}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="applytrail", description="Track job applications from Gmail."
    )
    parser.add_argument(
        "--offline", action="store_true", help="show saved data without contacting Gmail"
    )
    parser.add_argument("--version", action="version", version=f"applytrail {__version__}")
    args = parser.parse_args(argv)

    try:
        load_dotenv(find_dotenv(usecwd=True))
        settings = Settings.from_env()
    except Exception as error:
        _message(
            f"Unexpected error ({type(error).__name__}) while reading settings. "
            "Check .env and the APPLYTRAIL_* variables."
        )
        return 1
    out = Console()
    err = Console(stderr=True)
    try:
        if args.offline:
            # Implemented with US3 (T039).
            _message("--offline is not available yet.")
            return 1
        return _sync_command(settings, out, err)
    except AppError as error:
        _message(error.message)
        return error.exit_code
    except KeyboardInterrupt:
        # Ctrl-C before the sync started: nothing changed, nothing to save.
        _message(Interrupted().message)
        return Interrupted.exit_code
    except Exception:
        return _unexpected(settings)


def _sync_command(settings: Settings, out: Console, err: Console) -> int:
    # Network modules are imported here so the --offline path never loads them.
    from applytrail import extractor, mcp_client, sync

    ensure_home(settings)
    data = store.load(settings.store_path)
    model = extractor.OllamaExtractor(settings)
    model.check_ready()

    with err.status("Searching Gmail…") as status:

        def on_progress(k: int, total: int) -> None:
            if k == 0:
                if total > ESTIMATE_THRESHOLD:
                    minutes = max(1, total * SECONDS_PER_EMAIL // 60)
                    err.print(
                        f"{total} emails to process (~{minutes} min with local model). "
                        "Ctrl-C is safe; re-running continues where it stopped.",
                        soft_wrap=True,
                        highlight=False,
                    )
            elif k == 1:
                status.update(f"Loading {settings.model}…")
            else:
                status.update(f"Extracting {k}/{total}")

        try:
            with mcp_client.GmailMcp(settings) as mcp:
                counts = sync.run_sync(data, mcp, model, settings, datetime.now(UTC), on_progress)
        except KeyboardInterrupt:
            status.stop()
            store.save(data, settings.store_path)
            raise Interrupted() from None
        except AppError as error:
            status.stop()
            if error.exit_code in _SAVE_ON_EXIT:
                store.save(data, settings.store_path)
            if error.exit_code in _TABLE_ON_EXIT:
                render.render_table(data, out)
            raise

    # run_sync saved the completed store itself.
    render.render_table(data, out)
    render.render_summary(counts, out)
    return 0


def _message(text: str) -> None:
    """One unwrapped line on stderr (Rich would wrap long lines at the terminal width)."""
    print(text, file=sys.stderr)


def _unexpected(settings: Settings) -> int:
    error_type = type(sys.exc_info()[1]).__name__
    if not settings.debug:
        _message(f"Unexpected error ({error_type}). Set APPLYTRAIL_DEBUG=1 to write a debug log.")
        return 1
    try:
        ensure_home(settings)
        store.write_private(settings.debug_log_path, _traceback_without_messages())
    except OSError:
        _message(f"Unexpected error ({error_type}). Could not write the debug log.")
        return 1
    _message(f"Unexpected error ({error_type}). Details: {settings.debug_log_path}")
    return 1


def _traceback_without_messages() -> str:
    """Frames and exception types of the current exception chain, without messages.

    Exception text can quote email content, which must never be persisted (Principle V).
    """
    chain: list[BaseException] = []
    error = sys.exc_info()[1]
    while error is not None and error not in chain:
        chain.append(error)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    lines: list[str] = []
    for error in reversed(chain):
        lines.append("Traceback (most recent call last):\n")
        lines.extend(traceback.format_tb(error.__traceback__))
        lines.append(f"{type(error).__module__}.{type(error).__qualname__} (message omitted)\n")
    return "".join(lines)
