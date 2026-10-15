"""`applytrail`: sync new mail, save, print the table; `check` and `open` read the saved
store only (contracts/cli.md).

Expected failures print one line to stderr and exit with their code, never a stack trace
(Principle VII). The table goes to stdout; progress and messages go to stderr.
"""

import argparse
import sys
import traceback
from datetime import UTC, datetime

from dotenv import find_dotenv, load_dotenv
from rich.console import Console

from applytrail import __version__, links, lookup, render, store
from applytrail.config import Settings, ensure_home
from applytrail.errors import AppError, Interrupted

NO_DATA_MESSAGE = "No data yet. Run applytrail to sync."
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
    commands = parser.add_subparsers(dest="command", required=False)
    check = commands.add_parser(
        "check", help="check whether you already applied to a company (saved data only)"
    )
    check.add_argument("names", nargs="+", metavar="NAME", help="company name")
    open_ = commands.add_parser("open", help="open an application's Gmail thread")
    open_.add_argument("targets", nargs="+", metavar="TARGET", help="row number or company name")
    open_.add_argument(
        "--print", dest="print_only", action="store_true", help="print the address only"
    )
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
        if args.command == "check":
            return _check_command(settings, out, args.names)
        if args.command == "open":
            return _open_command(settings, out, args.targets, args.print_only)
        if args.offline:
            return _offline_command(settings, out)
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


def _offline_command(settings: Settings, out: Console) -> int:
    """Print the saved table and last-sync line; reads the store only, writes nothing."""
    data = store.load(settings.store_path)
    if not data.applications and data.sync.last_sync_at is None:
        _message(NO_DATA_MESSAGE)
        return 0
    render.render_table(data, out)
    render.render_last_sync(data.sync, out)
    return 0


def _check_command(settings: Settings, out: Console, names: list[str]) -> int:
    """Answer found (0) or not found (6) from the saved store; reads only, writes nothing."""
    data = store.load(settings.store_path)
    if not data.applications and data.sync.last_sync_at is None:
        _message(NO_DATA_MESSAGE)
        return 6
    result = lookup.find(data, " ".join(names))  # InvalidInput exits 2 via main
    if result.found:
        render.render_found(result, data, out)
        return 0
    render.render_not_found(result, data, out)
    return 6


def _open_command(settings: Settings, out: Console, targets: list[str], print_only: bool) -> int:
    """Print one application's thread address and open it where possible; writes nothing."""
    data = store.load(settings.store_path)
    if not data.applications and data.sync.last_sync_at is None:
        _message(NO_DATA_MESSAGE)
        return 6
    target = lookup.resolve(data, targets)  # InvalidInput exits 2 via main
    if isinstance(target, lookup.LookupResult):
        if not target.found:
            render.render_not_found(target, data, out)
            return 6
        if len(target.matches) > 1:
            out.print(render.build_check_table(data, target.matches))
            _message(f'Several applications match "{target.query}". Run: applytrail open <number>')
            return 2
        target = target.matches[0]
    url = links.thread_url(target.app.thread_id, data.sync.mailbox)
    launching = not print_only and links.can_launch_browser()
    render.render_open(target, url, launching, out)
    if launching and not links.open_in_browser(url):
        _message("Could not open a browser; use the address above.")
    return 0


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
