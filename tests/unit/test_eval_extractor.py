"""Scoring logic of scripts/eval_extractor.py (T024) with a fake extract function."""

import importlib.util
from pathlib import Path

import pytest

from applytrail.errors import ExtractionInvalid
from applytrail.models import Extraction

SCRIPT = Path(__file__).parents[2] / "scripts" / "eval_extractor.py"


@pytest.fixture(scope="module")
def ev():
    spec = importlib.util.spec_from_file_location("eval_extractor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(mid, is_job, company="", status="unknown"):
    return {
        "message_id": mid,
        "thread_id": f"t-{mid}",
        "date": "2026-10-01T10:00:00Z",
        "sender": "x@x.example",
        "subject": "s",
        "body_text": "b",
        "label": {"is_job_application": is_job, "company": company, "status": status},
    }


def answer(is_job, company="", status="unknown"):
    return Extraction(
        is_job_application=is_job, company=company, role=None, status=status, evidence=""
    )


def run(ev, cases, answers):
    def extract(email):
        result = answers[email.message_id]
        if isinstance(result, Exception):
            raise result
        return result

    ticks = iter(range(100))
    return ev.evaluate(ev.parse_cases(cases), extract, clock=lambda: next(ticks))


def test_all_correct_passes(ev):
    cases = [case("a", True, "Acme Inc.", "applied"), case("b", False)]
    answers = {"a": answer(True, "ACME Corporation", "applied"), "b": answer(False)}
    report = run(ev, cases, answers)
    assert report.company_accuracy == 1.0  # compared with norm_company
    assert report.status_accuracy == 1.0
    assert report.leaks == 0
    assert report.passed


def test_accuracy_is_over_job_emails_only(ev):
    cases = [case(str(i), True, "Acme", "applied") for i in range(10)] + [case("n", False)]
    answers = {str(i): answer(True, "Acme", "applied") for i in range(9)}
    answers["9"] = answer(True, "Globex", "rejected")
    answers["n"] = answer(False)
    report = run(ev, cases, answers)
    assert report.company_accuracy == pytest.approx(0.9)
    assert report.status_accuracy == pytest.approx(0.9)
    assert report.passed  # 90% is the threshold, inclusive


def test_below_90_fails(ev):
    cases = [case(str(i), True, "Acme", "applied") for i in range(10)]
    answers = {str(i): answer(True, "Acme", "applied") for i in range(8)}
    answers["8"] = answer(True, "Acme", "interview")
    answers["9"] = answer(True, "Acme", "interview")
    report = run(ev, cases, answers)
    assert report.company_accuracy == 1.0
    assert report.status_accuracy == pytest.approx(0.8)
    assert not report.passed


@pytest.mark.parametrize(
    "leaked",
    [
        lambda: answer(True, "Everyone", "offer"),
        lambda: answer(True, "Acme Corp", "applied"),
    ],
)
def test_non_job_with_usable_extraction_is_a_leak(ev, leaked):
    cases = [case("a", True, "Acme", "applied"), case("n", False)]
    report = run(ev, cases, {"a": answer(True, "Acme", "applied"), "n": leaked()})
    assert report.leaks == 1
    assert not report.passed


@pytest.mark.parametrize(
    "harmless",
    [
        lambda: answer(False),
        lambda: answer(True, "", "offer"),  # empty company: skipped, no row
        lambda: answer(True, "Acme", "unknown"),  # unknown status: skipped, no row
        lambda: ExtractionInvalid("x"),
    ],
    ids=["not-job", "no-company", "unknown-status", "invalid"],
)
def test_non_job_without_row_is_not_a_leak(ev, harmless):
    cases = [case("a", True, "Acme", "applied"), case("n", False)]
    report = run(ev, cases, {"a": answer(True, "Acme", "applied"), "n": harmless()})
    assert report.leaks == 0


def test_invalid_output_counts_as_skipped_and_wrong(ev):
    cases = [case("a", True, "Acme", "applied"), case("b", True, "Globex", "offer")]
    answers = {"a": answer(True, "Acme", "applied"), "b": ExtractionInvalid("bad json")}
    report = run(ev, cases, answers)
    assert report.skipped == 1
    assert report.company_accuracy == 0.5
    assert report.status_accuracy == 0.5


def test_job_email_without_row_is_wrong(ev):
    cases = [case("a", True, "Acme", "applied")]
    report = run(ev, cases, {"a": answer(False)})
    assert report.company_accuracy == 0.0
    assert report.status_accuracy == 0.0


def test_mean_seconds_per_email(ev):
    cases = [case("a", True, "Acme", "applied"), case("b", False)]
    report = run(ev, cases, {"a": answer(True, "Acme", "applied"), "b": answer(False)})
    assert report.mean_seconds == 1.0  # fake clock advances one tick per reading


def test_report_lists_mismatches_without_email_text(ev):
    cases = [case("a", True, "Acme", "applied")]
    report = run(ev, cases, {"a": answer(True, "Globex", "applied")})
    text = ev.format_report(report, "qwen3:4b")
    assert "a" in text and "Globex" in text
    assert "body_text" not in text
    assert "| qwen3:4b |" in text  # a row ready to paste into RESULTS.md


def test_golden_folder_loads(ev):
    cases = ev.parse_cases(ev.load_golden())
    assert len(cases) >= 30
