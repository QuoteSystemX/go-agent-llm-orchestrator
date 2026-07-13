#!/usr/bin/env python3
"""
Tests for STORY-1 memory-pressure trigger.

Covers:
  - _get_headroom_db_mb: returns None when db missing
  - _get_headroom_db_mb: returns float when db present
  - check_memory_pressure: False when under threshold
  - check_memory_pressure: True when over threshold
  - trigger_pressure_distill: invokes agent_squeeze + experience_distiller
  - action_daemon_status: includes memory block
"""
import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_DIR = REPO_ROOT / ".agent" / "scripts" / "orchestration" / "daemon"

# Load server module
_server_spec = importlib.util.spec_from_file_location(
    "daemon_server", str(DAEMON_DIR / "server.py")
)
daemon_server = importlib.util.module_from_spec(_server_spec)
sys.modules["daemon_server"] = daemon_server
_server_spec.loader.exec_module(daemon_server)
OrchestratorDaemon = daemon_server.OrchestratorDaemon
HEADROOM_DB = daemon_server.HEADROOM_DB
DEFAULT_MEMORY_PRESSURE_MB = daemon_server.DEFAULT_MEMORY_PRESSURE_MB


@pytest.fixture
def daemon():
    """Create an OrchestratorDaemon with a per-test temp dir for the headroom DB."""
    test_root = Path(tempfile.mkdtemp(prefix="pressure_test_"))
    fake_headroom = test_root / "headroom_memory.db"

    with patch.object(OrchestratorDaemon, "__init__", lambda self, socket_path=None: None), \
         patch.object(daemon_server, "REPO_ROOT", test_root), \
         patch.object(daemon_server, "HEADROOM_DB", fake_headroom):
        d = OrchestratorDaemon(socket_path=test_root / "sock")
        d.socket_path = test_root / "sock"
        d.graph = MagicMock()
        d.db = MagicMock()
        d.active_tasks = {}
        d.subscribers = {}
        d.shutting_down = False
        d.server = None

        async def _noop_shutdown(sig):
            pass
        d.shutdown = _noop_shutdown
        yield d, fake_headroom

    import shutil
    if test_root.exists():
        shutil.rmtree(test_root, ignore_errors=True)


def _patch_knowledge_modules(squeeze_mock, distill_module_mock):
    """Patch the knowledge submodules the daemon imports lazily."""
    fake_knowledge = MagicMock()
    fake_knowledge.agent_squeeze = squeeze_mock
    fake_knowledge.experience_distiller = distill_module_mock
    return patch.dict(sys.modules, {
        "knowledge": fake_knowledge,
        "knowledge.agent_squeeze": squeeze_mock,
        "knowledge.experience_distiller": distill_module_mock,
    })


class TestGetHeadroomDbMb:
    def test_returns_none_when_db_missing(self, daemon):
        d, fake_db = daemon
        assert d._get_headroom_db_mb() is None

    def test_returns_float_when_db_present(self, daemon):
        d, fake_db = daemon
        fake_db.write_bytes(b"\x00" * (3 * 1024 * 1024))  # 3 MB
        result = d._get_headroom_db_mb()
        assert result is not None
        assert 2.9 < result < 3.1


class TestCheckMemoryPressure:
    def test_false_when_db_missing(self, daemon):
        d, _ = daemon
        assert d.check_memory_pressure() is False

    def test_false_when_under_threshold(self, daemon):
        d, fake_db = daemon
        # Default threshold is 5 MB; create 1 MB db
        fake_db.write_bytes(b"\x00" * (1 * 1024 * 1024))
        assert d.check_memory_pressure() is False

    def test_true_when_over_threshold(self, daemon):
        d, fake_db = daemon
        # Default threshold is 5 MB; create 10 MB db
        fake_db.write_bytes(b"\x00" * (10 * 1024 * 1024))
        assert d.check_memory_pressure() is True

    def test_respects_env_override(self, daemon, monkeypatch):
        d, fake_db = daemon
        monkeypatch.setenv("DAEMON_MEMORY_PRESSURE_MB", "0.5")
        # Need to reimport the module to pick up the env var.
        # Instead, directly test the threshold logic via patched constant.
        fake_db.write_bytes(b"\x00" * (1 * 1024 * 1024))  # 1 MB
        with patch.object(daemon_server, "DEFAULT_MEMORY_PRESSURE_MB", 0.5):
            assert d.check_memory_pressure() is True


class TestTriggerPressureDistill:
    def test_invokes_both_steps(self, daemon):
        d, _ = daemon
        mock_squeeze = MagicMock()
        mock_distill = MagicMock()
        mock_distill.distill_lessons.return_value = "archived 5 lessons"

        with _patch_knowledge_modules(mock_squeeze, mock_distill):
            result = d.trigger_pressure_distill(reason="test")

        assert result["status"] in ("success", "partial")
        assert result["reason"] == "test"
        assert any(s["name"] == "agent_squeeze" for s in result["steps"])
        assert any(s["name"] == "experience_distiller" for s in result["steps"])
        mock_squeeze.main.assert_called_once()
        mock_distill.distill_lessons.assert_called_once()

    def test_partial_on_step_failure(self, daemon):
        d, _ = daemon
        mock_squeeze = MagicMock()
        mock_distill = MagicMock()
        mock_distill.distill_lessons.side_effect = RuntimeError("boom")

        with _patch_knowledge_modules(mock_squeeze, mock_distill):
            result = d.trigger_pressure_distill(reason="fail-test")

        assert result["status"] == "partial"
        sq_step = next(s for s in result["steps"] if s["name"] == "agent_squeeze")
        ed_step = next(s for s in result["steps"] if s["name"] == "experience_distiller")
        assert sq_step["status"] == "ok"
        assert ed_step["status"] == "error"
        assert "boom" in ed_step["error"]

    def test_includes_memory_size_after(self, daemon):
        d, fake_db = daemon
        fake_db.write_bytes(b"\x00" * (2 * 1024 * 1024))

        mock_squeeze = MagicMock()
        mock_distill = MagicMock(distill_lessons=MagicMock(return_value=""))
        with _patch_knowledge_modules(mock_squeeze, mock_distill):
            result = d.trigger_pressure_distill()

        assert result["headroom_db_mb_after"] is not None
        assert 1.9 < result["headroom_db_mb_after"] < 2.1


class TestActionDaemonStatusIncludesMemory:
    def test_memory_block_present(self, daemon):
        d, fake_db = daemon
        fake_db.write_bytes(b"\x00" * (3 * 1024 * 1024))
        d.shutting_down = False
        res = d.action_daemon_status()
        assert "memory" in res
        assert res["memory"]["pressure_threshold_mb"] == DEFAULT_MEMORY_PRESSURE_MB
        assert 2.9 < res["memory"]["headroom_db_mb"] < 3.1
        assert res["memory"]["under_pressure"] is False  # 3 MB < 5 MB default

    def test_under_pressure_flag(self, daemon):
        d, fake_db = daemon
        fake_db.write_bytes(b"\x00" * (10 * 1024 * 1024))
        res = d.action_daemon_status()
        assert res["memory"]["under_pressure"] is True

    def test_memory_block_when_db_missing(self, daemon):
        d, _ = daemon
        res = d.action_daemon_status()
        assert res["memory"]["headroom_db_mb"] is None
        assert res["memory"]["under_pressure"] is False


def teardown_module(module):
    # Per-test cleanup is handled by the daemon fixture; nothing global to do.
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
