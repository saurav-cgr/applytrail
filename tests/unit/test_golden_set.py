"""Shape of the golden set used by scripts/eval_extractor.py (T023, SC-003). No model call."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from applytrail.models import EmailMeta, Status

GOLDEN = Path(__file__).parents[1] / "golden"
FILES = sorted(GOLDEN.glob("*.json"))
CASES = [json.loads(p.read_text(encoding="utf-8")) for p in FILES]
EMAIL_FIELDS = {"message_id", "thread_id", "date", "sender", "subject", "body_text"}
# Applicant-tracking vendors appear by their real sending domains; everything else is made up.
ATS_DOMAINS = ("greenhouse.io", "lever.co", "myworkday.com", "ashbyhq.com", "smartrecruiters.com")


def test_at_least_30_cases():
    assert len(CASES) >= 30


def test_mix_of_job_and_non_job():
    jobs = [c for c in CASES if c["label"]["is_job_application"]]
    assert len(jobs) >= 18
    assert len(CASES) - len(jobs) >= 12


def test_every_status_is_covered():
    statuses = Counter(c["label"]["status"] for c in CASES if c["label"]["is_job_application"])
    assert set(statuses) == {s.value for s in Status}


def test_ats_senders_present():
    senders = " ".join(c["sender"] for c in CASES)
    for vendor in ("greenhouse.io", "lever.co", "myworkday.com"):
        assert vendor in senders


@pytest.mark.parametrize("case", CASES, ids=[p.stem for p in FILES])
def test_case_shape(case):
    assert set(case) == EMAIL_FIELDS | {"label"}
    EmailMeta.model_validate({k: case[k] for k in EMAIL_FIELDS})
    label = case["label"]
    assert set(label) == {"is_job_application", "company", "status"}
    if label["is_job_application"]:
        assert label["company"].strip()
        assert label["status"] in {s.value for s in Status}
    else:
        assert label == {"is_job_application": False, "company": "", "status": "unknown"}


@pytest.mark.parametrize("case", CASES, ids=[p.stem for p in FILES])
def test_only_made_up_addresses(case):
    for address in re.findall(r"[\w.+-]+@([\w.-]+)", case["sender"] + " " + case["body_text"]):
        assert address.endswith(".example") or address.endswith(ATS_DOMAINS), address


def test_message_ids_unique():
    ids = [c["message_id"] for c in CASES]
    assert len(ids) == len(set(ids))
