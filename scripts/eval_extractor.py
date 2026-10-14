"""Golden-set evaluation of the extractor against a live local model (manual; not run by CI).

    uv run python scripts/eval_extractor.py

Prints company accuracy, status accuracy, non-job leaks, skipped count and mean seconds per email
over tests/golden/*.json, plus a row to record in tests/golden/RESULTS.md. Exits 1 when accuracy
is below 90% or any non-job email would produce a row (SC-003). Email text is never printed.
"""

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from applytrail.config import Settings
from applytrail.errors import AppError, ExtractionInvalid
from applytrail.extractor import OllamaExtractor
from applytrail.merge import classify
from applytrail.models import EmailMeta, Extraction
from applytrail.normalize import norm_company

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden"
THRESHOLD = 0.9
EMAIL_FIELDS = ("message_id", "thread_id", "date", "sender", "subject", "body_text")


@dataclass
class Case:
    email: EmailMeta
    label: dict


@dataclass
class Report:
    job: int = 0
    non_job: int = 0
    company_correct: int = 0
    status_correct: int = 0
    leaks: int = 0
    skipped: int = 0
    seconds: list[float] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def company_accuracy(self) -> float:
        return self.company_correct / self.job if self.job else 0.0

    @property
    def status_accuracy(self) -> float:
        return self.status_correct / self.job if self.job else 0.0

    @property
    def mean_seconds(self) -> float:
        return sum(self.seconds) / len(self.seconds) if self.seconds else 0.0

    @property
    def passed(self) -> bool:
        return (
            self.company_accuracy >= THRESHOLD
            and self.status_accuracy >= THRESHOLD
            and self.leaks == 0
        )


def load_golden(folder: Path = GOLDEN) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def parse_cases(raw: list[dict]) -> list[Case]:
    return [
        Case(EmailMeta.model_validate({k: r[k] for k in EMAIL_FIELDS}), r["label"]) for r in raw
    ]


def makes_row(extraction: Extraction | None) -> bool:
    """True when the email would become a table row (the same rule the sync uses)."""
    return classify(extraction)[0] == "applied"


def evaluate(
    cases: list[Case],
    extract: Callable[[EmailMeta], Extraction],
    clock: Callable[[], float] = time.perf_counter,
) -> Report:
    report = Report()
    for case in cases:
        start = clock()
        try:
            got: Extraction | None = extract(case.email)
        except ExtractionInvalid:
            got = None
            report.skipped += 1
        report.seconds.append(clock() - start)

        label = case.label
        row = makes_row(got)
        if not label["is_job_application"]:
            report.non_job += 1
            if row:
                report.leaks += 1
                report.mismatches.append(f"{case.email.message_id}: non-job leaked as {_show(got)}")
            continue

        report.job += 1
        company_ok = row and norm_company(got.company) == norm_company(label["company"])
        status_ok = row and got.status == label["status"]
        report.company_correct += company_ok
        report.status_correct += status_ok
        if not (company_ok and status_ok):
            expected = f"{label['company']} / {label['status']}"
            report.mismatches.append(
                f"{case.email.message_id}: expected {expected}, got {_show(got)}"
            )
    return report


def _show(extraction: Extraction | None) -> str:
    if extraction is None:
        return "invalid output"
    if not extraction.is_job_application:
        return "not a job email"
    return f"{extraction.company or '(no company)'} / {extraction.status}"


def format_report(report: Report, model: str) -> str:
    lines = [
        f"Model: {model}",
        f"Emails: {report.job + report.non_job} ({report.job} job, {report.non_job} non-job)",
        f"Company accuracy: {report.company_accuracy:.1%}",
        f"Status accuracy: {report.status_accuracy:.1%}",
        f"Non-job leaks: {report.leaks}",
        f"Skipped (invalid output): {report.skipped}",
        f"Mean seconds per email: {report.mean_seconds:.2f}",
        f"Result: {'PASS' if report.passed else 'FAIL'}",
    ]
    if report.mismatches:
        lines += ["", "Mismatches:"] + [f"  {m}" for m in report.mismatches]
    lines += [
        "",
        "Row for tests/golden/RESULTS.md:",
        f"| {date.today().isoformat()} | {model} | {report.company_accuracy:.1%} | "
        f"{report.status_accuracy:.1%} | {report.leaks} | {report.skipped} | "
        f"{report.mean_seconds:.2f} | {'pass' if report.passed else 'fail'} |",
    ]
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    settings = Settings.from_env()
    extractor = OllamaExtractor(settings)
    try:
        extractor.check_ready()
        report = evaluate(parse_cases(load_golden()), extractor.extract)
    except AppError as err:
        print(err.message, file=sys.stderr)
        return err.exit_code
    print(format_report(report, settings.model))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
