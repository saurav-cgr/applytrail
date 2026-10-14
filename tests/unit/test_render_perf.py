"""`applytrail --offline` renders 500 applications in under 2 seconds (T040, SC-002)."""

import json
import time
from datetime import UTC, datetime, timedelta

from applytrail import cli
from applytrail.config import Settings
from applytrail.models import Application, Store

ROWS = 500
LIMIT_SECONDS = 2.0


def synthetic_store(n: int) -> Store:
    start = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    statuses = ["applied", "in_review", "assessment", "interview", "offer", "rejected"]
    data = Store.empty()
    for i in range(n):
        when = start - timedelta(hours=i)
        company = f"Company {i:03d} Holdings"
        key = f"company {i:03d} holdings|engineer {i % 7}"
        data.applications[key] = Application(
            key=key,
            company=company,
            role=f"Engineer {i % 7}",
            status=statuses[i % len(statuses)],
            last_activity=when,
            first_seen=when,
            thread_id=f"thr-{i:03d}",
            subject="Your application",
            evidence="We received your application",
            message_ids=[f"msg-{i:03d}"],
        )
    keys = sorted(data.applications)
    data.sync.added = keys[:20]
    data.sync.updated = keys[20:40]
    data.sync.last_sync_at = start
    data.sync.checkpoint = start
    data.sync.last_sync_complete = True
    data.sync.stop_reason = "complete"
    return data


def test_offline_renders_500_rows_under_2_seconds(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APPLYTRAIL_HOME", str(tmp_path / "home"))
    settings = Settings.from_env()
    settings.home.mkdir()
    settings.store_path.write_text(
        json.dumps(synthetic_store(ROWS).model_dump(mode="json")), encoding="utf-8"
    )

    started = time.perf_counter()
    code = cli.main(["--offline"])
    elapsed = time.perf_counter() - started

    out, _ = capsys.readouterr()
    assert code == 0
    assert out.count("Holdings") == ROWS
    assert elapsed < LIMIT_SECONDS, f"{elapsed:.2f} s for {ROWS} rows"
