#!/usr/bin/env python3
"""
Tests for STORY-2 INBOX v2.

Covers:
  - validate_entry: all required fields, all enum checks, regex patterns
  - validate_entry: conditional knowledge_anchor for redirect/context
  - append_entry: writes to JSONL, refuses invalid
  - read_entries: filters by intent/target/since
  - ack_entry: idempotent, marks acked, emits bus event
  - strip_for_prompt: sanitizes dangerous chars, respects max_chars
"""
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INBOX_PY = REPO_ROOT / ".agent" / "scripts" / "communication" / "inbox.py"

# Load module
_spec = importlib.util.spec_from_file_location("inbox_under_test", str(INBOX_PY))
mod = importlib.util.module_from_spec(_spec)
sys.modules["inbox_under_test"] = mod
_spec.loader.exec_module(mod)


@pytest.fixture
def fake_paths(tmp_path, monkeypatch):
    """Override INBOX_PATH, BUS_PATH, REPO_ROOT to a temp dir."""
    inbox_path = tmp_path / "INBOX.md"
    bus_path = tmp_path / "bus"
    bus_path.mkdir()
    monkeypatch.setattr(mod, "INBOX_PATH", inbox_path)
    monkeypatch.setattr(mod, "BUS_PATH", bus_path)
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    return inbox_path, bus_path


class TestValidateEntry:
    def test_valid_minimal(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "context",
            "body": "hello",
            "knowledge_anchor": "#section",
        }
        assert mod.validate_entry(e) == []

    def test_valid_with_anchor(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "redirect",
            "body": "see policy",
            "knowledge_anchor": "#error-handling",
        }
        assert mod.validate_entry(e) == []

    def test_missing_required(self):
        e = {"id": "x", "ts": "2026-07-11T12:00:00Z"}
        errs = mod.validate_entry(e)
        assert any("author" in err for err in errs)
        assert any("intent" in err for err in errs)
        assert any("body" in err for err in errs)

    def test_bad_id_pattern(self):
        e = {
            "id": "wrong-id",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "context",
            "body": "x",
        }
        errs = mod.validate_entry(e)
        assert any("id must match" in err for err in errs)

    def test_bad_ts_format(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "yesterday",
            "author": "human",
            "intent": "context",
            "body": "x",
        }
        errs = mod.validate_entry(e)
        assert any("ts must be ISO" in err for err in errs)

    def test_bad_intent(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "delete",  # not in allowed
            "body": "x",
        }
        errs = mod.validate_entry(e)
        assert any("intent must be" in err for err in errs)

    def test_body_too_long(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "context",
            "body": "x" * 2001,
        }
        errs = mod.validate_entry(e)
        assert any("exceeds max length" in err for err in errs)

    def test_redirect_without_anchor_rejected(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "redirect",
            "body": "switch to pgx",
        }
        errs = mod.validate_entry(e)
        assert any("requires knowledge_anchor" in err for err in errs)

    def test_context_without_anchor_rejected(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "context",
            "body": "see docs",
        }
        errs = mod.validate_entry(e)
        assert any("requires knowledge_anchor" in err for err in errs)

    def test_clarify_without_anchor_ok(self):
        e = {
            "id": "inb_20260711_120000_abcdef",
            "ts": "2026-07-11T12:00:00Z",
            "author": "human",
            "intent": "clarify",
            "body": "what is X?",
        }
        assert mod.validate_entry(e) == []


class TestAppendEntry:
    def test_writes_jsonl(self, fake_paths):
        inbox_path, _ = fake_paths
        entry = mod.append_entry("context", "see #docs", knowledge_anchor="#docs")
        assert inbox_path.exists()
        content = inbox_path.read_text(encoding="utf-8")
        assert content.endswith("\n")
        parsed = json.loads(content.strip().split("\n")[-1])
        assert parsed["id"] == entry.id
        assert parsed["body"] == "see #docs"

    def test_refuses_invalid(self, fake_paths):
        with pytest.raises(ValueError):
            mod.append_entry("redirect", "switch", knowledge_anchor=None)

    def test_generates_unique_ids(self, fake_paths):
        e1 = mod.append_entry("context", "a", knowledge_anchor="#a")
        e2 = mod.append_entry("context", "b", knowledge_anchor="#b")
        assert e1.id != e2.id


class TestReadEntries:
    def test_empty(self, fake_paths):
        assert mod.read_entries() == []

    def test_filters_by_intent(self, fake_paths):
        mod.append_entry("context", "c1", knowledge_anchor="#a")
        mod.append_entry("clarify", "c2")
        contexts = mod.read_entries(intent="context")
        assert len(contexts) == 1
        assert contexts[0].intent == "context"

    def test_filters_by_target(self, fake_paths):
        mod.append_entry("context", "c1", target="task_a", knowledge_anchor="#a")
        mod.append_entry("context", "c2", target="task_b", knowledge_anchor="#b")
        result = mod.read_entries(target="task_a")
        assert len(result) == 1
        assert result[0].target == "task_a"

    def test_filters_by_since(self, fake_paths):
        old = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        new = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)
        mod.append_entry("context", "old", knowledge_anchor="#a", ts=old)
        mod.append_entry("context", "new", knowledge_anchor="#b", ts=new)
        since = datetime(2026, 7, 5, tzinfo=timezone.utc)
        result = mod.read_entries(since=since)
        assert len(result) == 1
        assert result[0].body == "new"

    def test_skips_malformed_lines(self, fake_paths):
        inbox_path, _ = fake_paths
        inbox_path.write_text(
            "this is not JSON\n" +
            json.dumps({
                "id": "inb_20260711_120000_abcdef",
                "ts": "2026-07-11T12:00:00Z",
                "author": "human",
                "intent": "context",
                "body": "valid",
                "knowledge_anchor": "#a",
            }) + "\n",
            encoding="utf-8",
        )
        result = mod.read_entries()
        assert len(result) == 1
        assert result[0].body == "valid"


class TestAckEntry:
    def test_acks_existing(self, fake_paths):
        e = mod.append_entry("context", "x", knowledge_anchor="#a")
        assert mod.ack_entry(e.id) is True
        # Re-read shows acked
        result = mod.read_entries()
        assert result[0].acked_ts is not None
        assert result[0].acked_by == "agent"

    def test_idempotent_second_ack(self, fake_paths):
        e = mod.append_entry("context", "x", knowledge_anchor="#a")
        assert mod.ack_entry(e.id) is True
        assert mod.ack_entry(e.id) is False

    def test_ack_nonexistent(self, fake_paths):
        assert mod.ack_entry("inb_does_not_exist") is False

    def test_writes_bus_event(self, fake_paths):
        _, bus_path = fake_paths
        e = mod.append_entry("context", "x", knowledge_anchor="#a")
        mod.ack_entry(e.id)
        ack_log = bus_path / "inbox_acks.jsonl"
        assert ack_log.exists()
        events = [json.loads(line) for line in ack_log.read_text(encoding="utf-8").splitlines() if line]
        assert len(events) == 1
        assert events[0]["type"] == "inbox_ack"
        assert events[0]["entry_id"] == e.id


class TestStripForPrompt:
    def test_empty(self):
        assert mod.strip_for_prompt([]) == ""

    def test_sorts_ascending(self, fake_paths):
        e1 = mod.append_entry("context", "first", knowledge_anchor="#a",
                               ts=datetime(2026, 7, 11, 10, tzinfo=timezone.utc))
        e2 = mod.append_entry("context", "second", knowledge_anchor="#a",
                               ts=datetime(2026, 7, 11, 11, tzinfo=timezone.utc))
        out = mod.strip_for_prompt([e2, e1])  # passed in reverse order
        assert out.index("first") < out.index("second")

    def test_strips_dangerous_chars(self, fake_paths):
        e = mod.append_entry("context", "<script>alert(1)</script> `code` #h",
                             knowledge_anchor="#x")
        out = mod.strip_for_prompt([e])
        # The body is sanitized — markup chars are gone from the body part.
        # Extract the body part to verify.
        body_part = out.split("): ", 1)[1].split(" [anchor:")[0]
        assert "<script>" not in body_part
        assert "`" not in body_part
        assert "*" not in body_part
        assert "#" not in body_part
        # The body text "script" is preserved, just the dangerous chars removed
        assert "alert" in body_part
        assert "script" in body_part

    def test_respects_max_chars(self, fake_paths):
        entries = [
            mod.append_entry("context", "x" * 100, knowledge_anchor="#a",
                             ts=datetime(2026, 7, 11, 10, i, tzinfo=timezone.utc))
            for i in range(20)
        ]
        out = mod.strip_for_prompt(entries, max_chars=500)
        assert len(out) <= 500

    def test_includes_anchor(self, fake_paths):
        e = mod.append_entry("redirect", "see docs", knowledge_anchor="#errors")
        out = mod.strip_for_prompt([e])
        assert "anchor: #errors" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
