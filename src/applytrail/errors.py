"""Typed errors. Messages are copied from contracts/cli.md "Exit codes and messages"."""

from typing import Literal


class AppError(Exception):
    """An expected failure: the CLI prints `message` on one line and exits with `exit_code`."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthRequired(AppError):
    exit_code = 2

    def __init__(self) -> None:
        super().__init__("Gmail access not set up or expired. Run: applytrail-auth")


class ProviderNotRunning(AppError):
    exit_code = 2

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(
            f"Ollama is not running at {host}. Start the Ollama app or run: ollama serve"
        )


class ModelMissing(AppError):
    exit_code = 2

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"Model {model} is not installed. Run: ollama pull {model}")


class NetworkUnavailable(AppError):
    exit_code = 3

    def __init__(self) -> None:
        super().__init__("Cannot reach Gmail. Use applytrail --offline to view saved data.")


class ProviderUnavailable(AppError):
    exit_code = 4

    def __init__(
        self, reason: Literal["memory", "unresponsive"], model: str, pending: int = 0
    ) -> None:
        self.reason = reason
        self.model = model
        self.pending = pending
        if reason == "memory":
            message = (
                f"Not enough memory to run {model}. Close other apps or set APPLYTRAIL_MODEL "
                "to a smaller model (e.g. llama3.2:3b)."
            )
        else:
            message = (
                f"Ollama stopped responding. {pending} emails pending; progress saved. "
                "Run applytrail again."
            )
        super().__init__(message)


class GmailRateLimited(AppError):
    exit_code = 4

    def __init__(self, pending: int = 0) -> None:
        self.pending = pending
        super().__init__(
            f"Gmail rate limit reached. {pending} emails pending; progress saved. "
            "Try again in a few minutes."
        )


class StoreUnreadable(AppError):
    exit_code = 5

    def __init__(self, path: object) -> None:
        self.path = path
        super().__init__(f"Cannot read {path}. Move it aside and run applytrail to rebuild.")


class Interrupted(AppError):
    exit_code = 130

    def __init__(self) -> None:
        super().__init__("Interrupted. Progress saved.")


class GmailError(AppError):
    exit_code = 1

    def __init__(self, status: int | str) -> None:
        self.status = status
        super().__init__(f"Gmail returned an error (HTTP {status}). Try again later.")


class ExtractionInvalid(Exception):
    """The model's output failed validation. The email is skipped; this never exits the CLI."""
