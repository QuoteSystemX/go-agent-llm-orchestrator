#!/usr/bin/env python3
"""Tests for B5 telemetry_aggregator.py."""
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".agent" / "scripts" / "observability" / "telemetry_aggregator.py"

_spec = importlib.util.spec_from_file_location("telemetry_agg", str(SCRIPT))
mod = importlib.util.module_from_spec(_spec)
sys.modules["telemetry_agg"] = _spec.loader
_spec.loader.exec_module(mod)


@pytest.fixture
def fake_bus(tmp_path, monkeypatch):
    """Override BUS_DIR to a per-test temp dir."""
    bus = tmp_path / "bus"
    bus.mkdir()
    monkeypatch.setattr(mod, "BUS_DIR", bus)
    # Also override the EVENT_LOGS paths
    for name in mod.EVENT_LOGS:
        mod.EVENT_LOGS[name] = bus / Path(mod.EVENT_LOGS[name]).name
    return bus


class TestReadJsonl:
    def test_empty_file(self, fake_bus):
        events = mod._read_jsonl(fake_bus / "nonexistent.jsonl",
                                  datetime.now(timezone.utc))
        assert events == []

    def test_parses_valid_events(self, fake_bus):
        path = fake_bus / "test.jsonl"
        path.write_text(json.dumps({"ts": "2026-07-11T10:00:00Z", "value": 1}) + "\n"
                       + json.dumps({"ts": "2026-07-11T11:00:00Z", "value": 2}) + "\n",
                       encoding="utf-8")
        events = mod._read_jsonl(path, datetime(2026, 7, 1, tzinfo=timezone.utc))
        assert len(events) == 2

    def test_filters_old_events(self, fake_bus):
        path = fake_bus / "test.jsonl"
        path.write_text(json.dumps({"ts": "2025-01-01T10:00:00Z", "old": True}) + "\n"
                       + json.dumps({"ts": "2026-07-11T10:00:00Z", "new": True}) + "\n",
                       encoding="utf-8")
        events = mod._read_jsonl(path, datetime(2026, 7, 1, tzinfo=timezone.utc))
        assert len(events) == 1
        assert events[0].get("new") is True

    def test_skips_malformed_lines(self, fake_bus):
        path = fake_bus / "test.jsonl"
        path.write_text("not valid json\n"
                       + json.dumps({"ts": "2026-07-11T10:00:00Z", "valid": True}) + "\n",
                       encoding="utf-8")
        events = mod._read_jsonl(path, datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert len(events) == 1


class TestSentinelAge:
    def test_missing(self, fake_bus):
        info = mod._sentinel_age()
        assert info["exists"] is False

    def test_present(self, fake_bus, monkeypatch):
        # Create a sentinel file
        sentinel = fake_bus / ".distill_sentinel"
        sentinel.write_text('{"ts": "2026-07-11T10:00:00Z"}', encoding="utf-8")
        info = mod._sentinel_age()
        assert info["exists"] is True
        assert "age_seconds" in info
        assert "age_human" in info


class TestInjectionIndex:
    def test_empty(self, fake_bus):
        info = mod._injection_index()
        assert info["total"] == 0

    def test_with_data(self, fake_bus):
        idx_path = fake_bus / "knowledge_injections.json"
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        old = datetime.now(timezone.utc) - timedelta(days=40)
        idx = {
            "injections": [
                {"lesson_id": "L1", "scope": "global", "registered_ts": recent.isoformat(), "ttl_days": 30},
                {"lesson_id": "L2", "scope": "task:abc", "registered_ts": recent.isoformat(), "ttl_days": 30},
                {"lesson_id": "L3", "scope": "global", "registered_ts": old.isoformat(), "ttl_days": 30},
            ]
        }
        idx_path.write_text(json.dumps(idx), encoding="utf-8")
        info = mod._injection_index()
        assert info["total"] == 3
        assert info["active"] == 2
        assert info["stale"] == 1
        assert info["by_scope"]["global"] == 2
        assert info["by_scope"]["task:abc"] == 1


class TestHarnessStats:
    def test_empty(self):
        stats = mod._harness_stats([])
        assert stats["total_invocations"] == 0

    def test_with_spans(self):
        events = [
            {"attributes": {"harness.name": "claude", "exit.code": 0, "caller.role": "infra-agent", "duration.ms": 1000, "sandbox.violations": 0}},
            {"attributes": {"harness.name": "claude", "exit.code": 0, "caller.role": "infra-agent", "duration.ms": 2000, "sandbox.violations": 0}},
            {"attributes": {"harness.name": "free_code", "exit.code": 1, "caller.role": "squad-agent", "duration.ms": 500, "sandbox.violations": 1}},
        ]
        stats = mod._harness_stats(events)
        assert stats["total_invocations"] == 3
        assert stats["by_harness"]["claude"] == 2
        assert stats["by_harness"]["free_code"] == 1
        assert stats["by_caller"]["infra-agent"] == 2
        assert stats["avg_duration_ms"] == 1166.7  # (1000+2000+500)/3
        assert stats["sandbox_violations_total"] == 1


class TestCapabilityDenied:
    def test_empty(self):
        stats = mod._capability_denied_stats([])
        assert stats["total_denied"] == 0

    def test_with_denials(self):
        events = [
            {"action": "run_task", "caller_role": "session-agent", "required_capability": "modify-tasks"},
            {"action": "run_task", "caller_role": "session-agent", "required_capability": "modify-tasks"},
            {"action": "stop", "caller_role": "human", "required_capability": "stop-daemon"},
        ]
        stats = mod._capability_denied_stats(events)
        assert stats["total_denied"] == 3
        assert stats["by_action"]["run_task"] == 2
        assert stats["by_role"]["session-agent"] == 2
        assert stats["by_cap"]["modify-tasks"] == 2


class TestAggregate:
    def test_full_aggregation(self, fake_bus, monkeypatch):
        # Setup fake events using the actual EVENT_LOGS file names
        recent = datetime.now(timezone.utc).isoformat()
        # harness_invoke maps to otel_spans.jsonl
        mod.EVENT_LOGS["harness_invoke"].write_text(
            json.dumps({"ts": recent, "attributes": {"harness.name": "claude", "exit.code": 0, "duration.ms": 100, "caller.role": "infra-agent", "sandbox.violations": 0}}) + "\n",
            encoding="utf-8",
        )
        mod.EVENT_LOGS["inbox_ack"].write_text(
            json.dumps({"ts": recent, "entry_id": "inb_x", "acked_by": "human"}) + "\n",
            encoding="utf-8",
        )
        mod.EVENT_LOGS["capability_denied"].write_text(
            json.dumps({"ts": recent, "action": "run_task", "caller_role": "session-agent", "required_capability": "modify-tasks"}) + "\n",
            encoding="utf-8",
        )
        result = mod.aggregate(window_hours=24)
        assert result["metadata"]["window_hours"] == 24
        assert "distill_sentinel" in result
        assert "knowledge_injections" in result
        assert result["harness_invocations"]["total_invocations"] == 1
        assert result["inbox_acks"]["total_acks"] == 1
        assert result["capability_denied"]["total_denied"] == 1


class TestHumanizeDuration:
    def test_seconds(self):
        assert mod._humanize_duration(30) == "30s"

    def test_minutes(self):
        assert mod._humanize_duration(120) == "2m"

    def test_hours(self):
        assert mod._humanize_duration(3600) == "1h"

    def test_days(self):
        assert mod._humanize_duration(86400) == "1d"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
