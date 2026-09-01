#!/usr/bin/env python3
"""
Tests for STORY-1 pressure-triggered distillation.

Covers:
  - trigger_pressure_distill: invokes agent_squeeze + experience_distiller
  - trigger_pressure_distill: reports partial status on step failure
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


@pytest.fixture
def daemon():
    """Create an OrchestratorDaemon with a per-test temp dir."""
    test_root = Path(tempfile.mkdtemp(prefix="pressure_test_"))

    with patch.object(OrchestratorDaemon, "__init__", lambda self, socket_path=None: None), \
         patch.object(daemon_server, "REPO_ROOT", test_root):
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
        yield d

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


class TestTriggerPressureDistill:
    def test_invokes_both_steps(self, daemon):
        d = daemon
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
        d = daemon
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


def teardown_module(module):
    # Per-test cleanup is handled by the daemon fixture; nothing global to do.
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
