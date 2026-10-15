"""Local store load/save (contracts/store-schema.md, research R6)."""

import json
import os
import stat
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from applytrail import store
from applytrail.errors import StoreUnreadable
from applytrail.models import Application, ProcessedEmail, Status, Store

NOW = datetime(2026, 10, 12, 14, 3, tzinfo=UTC)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "home" / "applications.json"


def sample_store():
    s = Store.empty()
    s.applications["acme|backend engineer"] = Application(
        key="acme|backend engineer",
        company="Acme Inc.",
        role="Backend Engineer",
        status=Status.INTERVIEW,
        last_activity=NOW,
        first_seen=NOW,
        thread_id="t1",
        subject="Interview invitation",
        evidence="We'd like to invite you",
        message_ids=["m1"],
    )
    s.processed["m1"] = ProcessedEmail(
        message_id="m1", date=NOW, outcome="applied", application_key="acme|backend engineer"
    )
    s.sync.checkpoint = NOW
    return s


def test_missing_file_loads_empty(path):
    assert store.load(path) == Store.empty()


def test_round_trip(path):
    s = sample_store()
    store.save(s, path)
    assert store.load(path) == s


def test_format_indent_and_sorted_keys(path):
    s = sample_store()
    store.save(s, path)
    text = path.read_text(encoding="utf-8")
    expected = json.dumps(s.model_dump(mode="json"), indent=2, sort_keys=True)
    assert text.rstrip("\n") == expected
    assert '\n  "applications": {' in text


def test_saving_same_state_twice_is_byte_identical(path):
    s = sample_store()
    store.save(s, path)
    first = path.read_bytes()
    store.save(store.load(path), path)
    assert path.read_bytes() == first


def test_file_and_folder_modes(path):
    store.save(sample_store(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_save_uses_tmp_then_replace(path, monkeypatch):
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((os.fspath(src), os.fspath(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    store.save(sample_store(), path)
    assert calls == [(os.fspath(path.with_name("applications.json.tmp")), os.fspath(path))]
    assert not path.with_name("applications.json.tmp").exists()


def test_failed_replace_leaves_original_intact(path, monkeypatch):
    store.save(Store.empty(), path)
    original = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save(sample_store(), path)
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "content",
    [
        b"{not json",
        b'{"schema_version": 1, "applications": {}}',
        json.dumps({**Store.empty().model_dump(mode="json"), "schema_version": 2}).encode(),
        json.dumps({**Store.empty().model_dump(mode="json"), "schema_version": True}).encode(),
        json.dumps({**Store.empty().model_dump(mode="json"), "schema_version": 1.0}).encode(),
    ],
    ids=[
        "invalid-json",
        "validation-failure",
        "unknown-schema-version",
        "boolean-schema-version",
        "float-schema-version",
    ],
)
def test_unreadable_store_raises_and_is_untouched(path, content):
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    with pytest.raises(StoreUnreadable) as info:
        store.load(path)
    assert str(path) in info.value.message
    assert info.value.exit_code == 5
    assert path.read_bytes() == content


def test_saved_json_never_contains_body_text(path):
    store.save(sample_store(), path)
    assert "body_text" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "content",
    [b"{corrupt", b'{"schema_version": 2, "applications": {}}'],
    ids=["invalid-json", "validation-failure"],
)
def test_save_refuses_to_overwrite_unreadable_store(path, content):
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    with pytest.raises(StoreUnreadable) as info:
        store.save(Store.empty(), path)
    assert info.value.exit_code == 5
    assert path.read_bytes() == content
    assert not path.with_name("applications.json.tmp").exists()


def test_save_refuses_invalid_store(path):
    store.save(Store.empty(), path)
    original = path.read_bytes()
    bad = Store.empty()
    bad.sync.last_sync_complete = True
    bad.sync.pending = 5
    with pytest.raises(ValidationError):
        store.save(bad, path)
    assert path.read_bytes() == original


def test_stale_tmp_file_is_replaced(path):
    path.parent.mkdir(parents=True)
    tmp = path.with_name("applications.json.tmp")
    tmp.write_bytes(b"leftover from a crash")
    store.save(sample_store(), path)
    assert store.load(path) == sample_store()
    assert not tmp.exists()


def test_tmp_symlink_cannot_truncate_original(path, monkeypatch):
    store.save(sample_store(), path)
    original = path.read_bytes()
    path.with_name("applications.json.tmp").symlink_to(path)

    def boom(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save(Store.empty(), path)
    assert path.read_bytes() == original


def test_store_without_mailbox_key_loads_with_none(path):
    store.save(sample_store(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["sync"]["mailbox"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert store.load(path).sync.mailbox is None


def test_saving_same_mailbox_twice_is_byte_identical(path):
    s = sample_store()
    s.sync.mailbox = "me+jobs@example.com"
    store.save(s, path)
    first = path.read_bytes()
    store.save(store.load(path), path)
    assert path.read_bytes() == first
    assert b'"mailbox": "me+jobs@example.com"' in first
