#!/usr/bin/env python3
"""
Tests for STORY-4 capability_check wired into daemon IPC.

Covers:
  - _check_capability: allows when role has the capability
  - _check_capability: denies when role lacks the capability
  - _check_capability: fail-open when matrix is missing
  - ACTION_CAPABILITY_MAP: maps run_task, stop, trigger_distill to caps
  - handle_client: enforces cap check on privileged actions
  - handle_client: passes through for read-only actions (status, daemon_status)
  - handle_client: returns CAPABILITY_DENIED with code
"""
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_DIR = REPO_ROOT / ".agent" / "scripts" / "orchestration" / "daemon"
PERMISSIONS_DIR = REPO_ROOT / ".agent" / "scripts" / "permissions"

_server_spec = importlib.util.spec_from_file_location(
    "daemon_server", str(DAEMON_DIR / "server.py")
)
daemon_server = importlib.util.module_from_spec(_server_spec)
sys.modules["daemon_server"] = _server_spec.loader
_server_spec.loader.exec_module(daemon_server)
OrchestratorDaemon = daemon_server.OrchestratorDaemon


VALID_CAP_YAML = """
version: "1.0.0"
roles:
  infra-agent:
    capabilities:
      - { cap: modify-tasks, scope: global }
      - { cap: stop-daemon, scope: global }
      - { cap: trigger-distill, scope: global }
  squad-agent:
    capabilities:
      - { cap: modify-tasks, scope: global }
  session-agent:
    capabilities: []
  human:
    capabilities:
      - { cap: stop-daemon, scope: global }
operations:
  run_task: modify-tasks
  stop: stop-daemon
  trigger_distill: trigger-distill
"""


@pytest.fixture
def daemon_with_caps():
    """Daemon with mocked DB, REPO_ROOT, and a per-test capabilities.yaml."""
    test_root = Path(tempfile.mkdtemp(prefix="daemon_caps_"))
    cap_yaml = test_root / "capabilities.yaml"
    cap_yaml.write_text(VALID_CAP_YAML, encoding="utf-8")

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

        def _noop_shutdown(sig):
            pass
        d.shutdown = _noop_shutdown

        # Patch capability_check module to read from test_root
        cap_spec = importlib.util.spec_from_file_location(
            "capability_check", str(PERMISSIONS_DIR / "capability_check.py")
        )
        cap_mod = importlib.util.module_from_spec(cap_spec)
        sys.modules["capability_check"] = cap_mod
        cap_spec.loader.exec_module(cap_mod)
        cap_mod.MATRIX_PATH = cap_yaml
        cap_mod.REPO_ROOT = test_root

        yield d, test_root, cap_yaml

    import shutil
    shutil.rmtree(test_root, ignore_errors=True)


class TestCheckCapability:
    def test_infra_agent_allowed(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("infra-agent", "modify-tasks", "global")
        assert result is None  # None = allowed

    def test_session_agent_denied(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("session-agent", "modify-tasks", "global")
        assert result is not None
        assert result["code"] == "CAPABILITY_DENIED"
        assert result["caller_role"] == "session-agent"
        assert result["required_capability"] == "modify-tasks"

    def test_squad_agent_allowed_for_modify_tasks(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        assert d._check_capability("squad-agent", "modify-tasks", "global") is None

    def test_squad_agent_denied_for_stop(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("squad-agent", "stop-daemon", "global")
        assert result is not None
        assert result["code"] == "CAPABILITY_DENIED"

    def test_human_allowed_for_stop(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        assert d._check_capability("human", "stop-daemon", "global") is None

    def test_human_denied_for_modify_tasks(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("human", "modify-tasks", "global")
        assert result is not None
        assert result["code"] == "CAPABILITY_DENIED"

    def test_unknown_role_denied(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("no-such-role", "stop-daemon", "global")
        assert result is not None

    def test_unknown_capability_denied(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        result = d._check_capability("infra-agent", "no-such-cap", "global")
        assert result is not None

    def test_fail_open_when_matrix_missing(self, daemon_with_caps):
        d, test_root, cap_yaml = daemon_with_caps
        # Delete the matrix file
        cap_yaml.unlink()
        result = d._check_capability("session-agent", "modify-tasks", "global")
        # Fail-open: returns None (allowed) when matrix can't be loaded
        assert result is None


class TestActionCapabilityMap:
    def test_run_task_requires_modify_tasks(self):
        assert OrchestratorDaemon.ACTION_CAPABILITY_MAP["run_task"] == "modify-tasks"

    def test_stop_requires_stop_daemon(self):
        assert OrchestratorDaemon.ACTION_CAPABILITY_MAP["stop"] == "stop-daemon"

    def test_trigger_distill_requires_trigger_distill(self):
        assert OrchestratorDaemon.ACTION_CAPABILITY_MAP["trigger_distill"] == "trigger-distill"

    def test_status_not_in_map(self):
        """Read-only actions don't need a capability check."""
        assert "status" not in OrchestratorDaemon.ACTION_CAPABILITY_MAP
        assert "daemon_status" not in OrchestratorDaemon.ACTION_CAPABILITY_MAP
        assert "scan_graph" not in OrchestratorDaemon.ACTION_CAPABILITY_MAP


class TestHandleClientEnforcesCap:
    """Integration: the cap check actually fires inside handle_client."""

    def test_session_agent_run_task_denied(self, daemon_with_caps):
        d, _, _ = daemon_with_caps
        async def runner():
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            reader.feed_data(
                json.dumps({
                    "action": "run_task",
                    "task_id": "task_x",
                    "task": "do something",
                    "caller_role": "session-agent",
                }).encode() + b"\n"
            )
            reader.feed_eof()
            writer = MagicMock()
            writer.write = MagicMock()
            async def _drain(): pass
            writer.drain = _drain
            writer.close = MagicMock()
            async def _wc(): pass
            writer.wait_closed = _wc

            await d.handle_client(reader, writer)

            assert writer.write.called
            written = writer.write.call_args[0][0].decode()
            response = json.loads(written.strip())
            assert response["code"] == "CAPABILITY_DENIED"
            assert response["caller_role"] == "session-agent"

        asyncio.run(runner())

    def test_infra_agent_run_task_allowed(self, daemon_with_caps):
        """infra-agent can run tasks (default caller_role)."""
        d, _, _ = daemon_with_caps
        d.db.acquire_lock.return_value = True

        async def runner():
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            reader.feed_data(
                json.dumps({
                    "action": "run_task",
                    "task_id": "task_y",
                    "task": "do something",
                    "caller_role": "infra-agent",
                }).encode() + b"\n"
            )
            reader.feed_eof()
            writer = MagicMock()
            writer.write = MagicMock()
            async def _drain(): pass
            writer.drain = _drain
            writer.close = MagicMock()
            async def _wc(): pass
            writer.wait_closed = _wc

            with patch.object(daemon_server, "TaskState") as mock_state:
                mock_state.return_value.model_dump.return_value = {"status": "planning"}
                await d.handle_client(reader, writer)

            assert writer.write.called
            written = writer.write.call_args_list[-1][0][0].decode()
            response = json.loads(written.strip())
            assert response.get("code") != "CAPABILITY_DENIED"

        asyncio.run(runner())

    def test_status_action_no_cap_check(self, daemon_with_caps):
        """Read-only actions (status, daemon_status) skip the cap check."""
        d, _, _ = daemon_with_caps
        d.db.load_task.return_value = {"status": "completed", "task_id": "task_z"}

        async def runner():
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            reader.feed_data(
                json.dumps({
                    "action": "status",
                    "task_id": "task_z",
                    "caller_role": "session-agent",
                }).encode() + b"\n"
            )
            reader.feed_eof()
            writer = MagicMock()
            writer.write = MagicMock()
            async def _drain(): pass
            writer.drain = _drain
            writer.close = MagicMock()
            async def _wc(): pass
            writer.wait_closed = _wc

            await d.handle_client(reader, writer)

            written = writer.write.call_args[0][0].decode()
            response = json.loads(written.strip())
            assert response.get("code") != "CAPABILITY_DENIED"
            assert response.get("status") == "success"
            assert response.get("task", {}).get("status") == "completed"

        asyncio.run(runner())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
