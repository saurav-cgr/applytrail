"""Exit codes and messages from contracts/cli.md."""

import pytest

from applytrail.errors import (
    AppError,
    AuthRequired,
    ExtractionInvalid,
    GmailError,
    GmailRateLimited,
    Interrupted,
    ModelMissing,
    NetworkUnavailable,
    ProviderNotRunning,
    ProviderUnavailable,
    StoreUnreadable,
)


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (AuthRequired(), 2, "Gmail access not set up or expired. Run: applytrail-auth"),
        (
            ProviderNotRunning("http://127.0.0.1:11434"),
            2,
            "Ollama is not running at http://127.0.0.1:11434. "
            "Start the Ollama app or run: ollama serve",
        ),
        (ModelMissing("qwen3:4b"), 2, "Model qwen3:4b is not installed. Run: ollama pull qwen3:4b"),
        (
            NetworkUnavailable(),
            3,
            "Cannot reach Gmail. Use applytrail --offline to view saved data.",
        ),
        (
            ProviderUnavailable("unresponsive", "qwen3:4b", pending=7),
            4,
            "Ollama stopped responding. 7 emails pending; progress saved. Run applytrail again.",
        ),
        (
            ProviderUnavailable("memory", "qwen3:4b"),
            4,
            "Not enough memory to run qwen3:4b. Close other apps or set APPLYTRAIL_MODEL to a "
            "smaller model (e.g. llama3.2:3b).",
        ),
        (
            GmailRateLimited(pending=3),
            4,
            "Gmail rate limit reached. 3 emails pending; progress saved. "
            "Try again in a few minutes.",
        ),
        (
            StoreUnreadable("/data/applications.json"),
            5,
            "Cannot read /data/applications.json. Move it aside and run applytrail to rebuild.",
        ),
        (Interrupted(), 130, "Interrupted. Progress saved."),
    ],
)
def test_exit_codes_and_messages(error, code, message):
    assert isinstance(error, AppError)
    assert error.exit_code == code
    assert error.message == message
    assert str(error) == message


def test_gmail_error_exit_1_names_status():
    err = GmailError(503)
    assert err.exit_code == 1
    assert "503" in err.message


def test_extraction_invalid_is_not_an_app_error():
    assert not issubclass(ExtractionInvalid, AppError)


def test_invalid_input_carries_its_message_and_exits_2():
    from applytrail.errors import InvalidInput

    error = InvalidInput("Enter a company name, for example: applytrail check acme")
    assert isinstance(error, AppError)
    assert error.exit_code == 2
    assert error.message == "Enter a company name, for example: applytrail check acme"
