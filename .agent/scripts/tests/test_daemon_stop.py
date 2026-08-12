#!/usr/bin/env python3
"""
Tests for STORY-3.3 SIGTERM channel.

Covers:
  - action_daemon_status: returns running/draining based on flag
  - action_stop: flips to draining, returns ACK with in-flight list
  - action_stop: idempotent (second call returns same state without side effects)
  - action_run_task: refuses new tasks when daemon is draining
  - bus event: action_stop persists stop event to .agent/bus/daemon_stop.jsonl
"""
import asyncio
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_DIR = REPO_ROOT / ".agent" / "scripts" / "orchestration" / "daemon"

# Load server module explicitly via importlib (pytest's sys.path manipulation
# makes `from server import ...` unreliable for files in subdirs).
import importlib.util as _il
_server_spec = _il.spec_from_file_location("daemon_server", str(DAEMON_DIR / "server.py"))
daemon_server = _il.module_from_spec(_server_spec)
sys.modules["daemon_server"] = daemon_server
_server_spec.loader.exec_module(daemon_server)
OrchestratorDaemon = daemon_server.OrchestratorDaemon

# Use a tempdir as REPO_ROOT for the daemon instance so we don't pollute the
# real .agent/bus with test events.
TEST_ROOT = Path(tempfile.mkdtemp(prefix="daemon_stop_test_"))
BUS_DIR = TEST_ROOT / ".agent" / "bus"
BUS_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH = TEST_ROOT / ".agent" / "bus" / "orchestrator.sock"


@pytest.fixture
def daemon():
    """Create an OrchestratorDaemon with patched REPO_ROOT and DB."""
    with patch.object(OrchestratorDaemon, "__init__", lambda self, socket_path=None: None), \
         patch.object(daemon_server, "REPO_ROOT", TEST_ROOT), \
         patch.object(daemon_server, "SOCKET_PATH", SOCKET_PATH):
        d = OrchestratorDaemon(socket_path=SOCKET_PATH)
        d.socket_path = SOCKET_PATH
        d.graph = MagicMock()  # Avoid init_graph's expensive agent scan
        d.db = MagicMock()
        d.active_tasks = {}
        d.subscribers = {}
        d.shutting_down = False
        d.server = None  # shutdown() checks this; real daemon sets it in start()
        # Replace shutdown with a no-op async so action_stop's background
        # task doesn't try to do real cleanup work in unit tests.
        async def _noop_shutdown(sig):
            pass
        d.shutdown = _noop_shutdown
        yield d
    # Cleanup
    import shutil
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT, ignore_errors=True)


class TestDaemonStatus:
    """action_daemon_status reports the current state machine."""

    def test_running_state(self, daemon):
        daemon.shutting_down = False
        res = daemon.action_daemon_status()
        assert res["status"] == "success"
        assert res["state"] == "running"
        assert res["active_tasks"] == []
        assert str(SOCKET_PATH) in res["socket_path"]

    def test_draining_state(self, daemon):
        daemon.shutting_down = True
        res = daemon.action_daemon_status()
        assert res["status"] == "success"
        assert res["state"] == "draining"

    def test_includes_active_task_ids(self, daemon):
        daemon.active_tasks = {"task_abc": MagicMock(), "task_xyz": MagicMock()}
        res = daemon.action_daemon_status()
        assert set(res["active_tasks"]) == {"task_abc", "task_xyz"}


class TestActionStop:
    """action_stop flips to draining, ACKs caller, and persists audit event."""

    def test_first_call_acknowledges(self, daemon):
        async def runner():
            return await daemon.action_stop("user pressed Ctrl+C")

        res = asyncio.run(runner())
        assert res["status"] == "success"
        assert res["state"] == "draining"
        assert daemon.shutting_down is True
        assert "user pressed Ctrl+C" in res["reason"]
        assert res["active_tasks_in_flight"] == []

    def test_idempotent_second_call(self, daemon):
        daemon.shutting_down = True
        async def runner():
            return await daemon.action_stop("second call")

        res = asyncio.run(runner())
        # Already draining — return the same shape without re-acknowledging.
        assert res["status"] == "success"
        assert res["state"] == "draining"
        assert "already shutting down" in res["message"]

    def test_persists_audit_event(self, daemon):
        async def runner():
            return await daemon.action_stop("audit me")

        asyncio.run(runner())
        stop_file = BUS_DIR / "daemon_stop.jsonl"
        assert stop_file.exists(), f"Expected audit log at {stop_file}"

        lines = stop_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["type"] == "daemon_stop"
        assert event["author"] == "daemon.action_stop"
        assert event["reason"] == "audit me"
        assert "ts" in event
        assert event["id"].startswith("stop_")

    def test_active_tasks_captured_in_audit(self, daemon):
        daemon.active_tasks = {"task_42": MagicMock()}

        async def runner():
            return await daemon.action_stop("test")

        asyncio.run(runner())
        stop_file = BUS_DIR / "daemon_stop.jsonl"
        event = json.loads(stop_file.read_text(encoding="utf-8").strip().split("\n")[-1])
        assert event["active_tasks_at_stop"] == ["task_42"]


class TestActionRunTaskRefusesDuringDrain:
    """The gate in action_run_task: refuses new work when daemon is draining."""

    def test_refuses_when_draining(self, daemon):
        daemon.shutting_down = True
        async def runner():
            return await daemon.action_run_task("task_new", "do something", dry_run=False)

        res = asyncio.run(runner())
        assert res["status"] == "error"
        assert res["code"] == "DAEMON_DRAINING"
        assert "draining" in res["message"].lower()

    def test_allows_when_running(self, daemon):
        # Mock db to simulate lock acquisition
        daemon.db.acquire_lock.return_value = True
        daemon.db.load_task.return_value = None

        # Patch TaskState and the actual execution engine to avoid real work
        with patch.object(daemon_server, "TaskState") as mock_state:
            mock_state.return_value.model_dump.return_value = {"status": "planning"}
            async def runner():
                return await daemon.action_run_task("task_new", "do something", dry_run=True)

            # This will eventually try to spawn a real asyncio task against
            # ExecutionEngine; we just need to confirm the draining gate is
            # NOT what blocks us. The test may raise deeper down; we only
            # assert the gate wasn't the cause.
            try:
                res = asyncio.run(runner())
                # If we got a response, ensure it's not the draining error.
                assert res.get("code") != "DAEMON_DRAINING"
            except (RuntimeError, AttributeError):
                # Engine setup not fully mocked — that's fine; the point is
                # we did NOT short-circuit at the draining gate.
                pass

    def test_validates_input_even_when_draining(self, daemon):
        daemon.shutting_down = True
        async def runner():
            return await daemon.action_run_task("", "do something", dry_run=False)

        res = asyncio.run(runner())
        # Input validation runs BEFORE the draining check
        assert res["status"] == "error"
        assert "Missing task_id" in res["message"]


class TestFallbackStopFile:
    """STORY-3.3 gate G: the daemon must actually read the file `bin/stop
    --kill` writes, not just leave it on disk. Previously nothing did —
    bin/stop's own comment claimed a "5s tick" that didn't exist anywhere
    in server.py. Found in the 2026-08-12 audit."""

    def test_clear_stale_stop_file_removes_pre_existing_file(self, daemon, tmp_path):
        stop_file = tmp_path / "STOP"
        stop_file.write_text("stale", encoding="utf-8")
        with patch.object(daemon_server, "FALLBACK_STOP_FILE", stop_file):
            daemon._clear_stale_stop_file()
        assert not stop_file.exists()

    def test_clear_stale_stop_file_noop_when_absent(self, daemon, tmp_path):
        stop_file = tmp_path / "STOP"
        with patch.object(daemon_server, "FALLBACK_STOP_FILE", stop_file):
            daemon._clear_stale_stop_file()  # must not raise
        assert not stop_file.exists()

    def test_watcher_triggers_shutdown_when_file_appears(self, daemon, tmp_path):
        stop_file = tmp_path / "STOP"
        stop_file.write_text("kill: test reason\n", encoding="utf-8")

        shutdown_calls = []
        async def _record_shutdown(sig):
            shutdown_calls.append(sig)
        daemon.shutdown = _record_shutdown

        with patch.object(daemon_server, "FALLBACK_STOP_FILE", stop_file):
            asyncio.run(daemon._watch_fallback_stop_file())

        assert shutdown_calls == [daemon_server.signal.SIGTERM]
        assert not stop_file.exists(), "STOP file must be removed before/at shutdown, not left behind"

    def test_watcher_persists_distinct_audit_event(self, daemon, tmp_path):
        stop_file = tmp_path / "STOP"
        stop_file.write_text("kill: audit test\n", encoding="utf-8")

        async def _noop_shutdown(sig):
            pass
        daemon.shutdown = _noop_shutdown

        with patch.object(daemon_server, "FALLBACK_STOP_FILE", stop_file):
            asyncio.run(daemon._watch_fallback_stop_file())

        stop_log = BUS_DIR / "daemon_stop.jsonl"
        events = [json.loads(l) for l in stop_log.read_text(encoding="utf-8").strip().split("\n")]
        fallback_events = [e for e in events if e["type"] == "daemon_stop_fallback"]
        assert len(fallback_events) == 1
        assert "audit test" in fallback_events[0]["reason"]
        # Distinct from action_stop's own event, so it's clear which path fired.
        assert fallback_events[0]["author"] == "daemon._watch_fallback_stop_file"

    def test_watcher_takes_no_action_when_file_absent(self, daemon, tmp_path):
        stop_file = tmp_path / "STOP"  # never created

        shutdown_calls = []
        async def _record_shutdown(sig):
            shutdown_calls.append(sig)
        daemon.shutdown = _record_shutdown

        async def runner():
            with patch.object(daemon_server, "FALLBACK_STOP_FILE", stop_file), \
                 patch.object(daemon_server, "FALLBACK_STOP_POLL_INTERVAL_S", 0.01):
                task = asyncio.create_task(daemon._watch_fallback_stop_file())
                await asyncio.sleep(0.05)  # several poll cycles
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        asyncio.run(runner())
        assert shutdown_calls == []


class TestBinStopCLI:
    """bin/stop end-to-end behavior (no real daemon — mocks send_ipc_request)."""

    @pytest.fixture
    def bin_stop_module(self):
        """Load bin/stop as a module via importlib.

        bin/stop has no .py extension, so we need an explicit SourceFileLoader.
        """
        import importlib.util
        import importlib.machinery
        bin_stop_path = REPO_ROOT / "bin" / "stop"
        loader = importlib.machinery.SourceFileLoader(
            "bin_stop_under_test", str(bin_stop_path)
        )
        spec = importlib.util.spec_from_loader("bin_stop_under_test", loader)
        if spec is None:
            pytest.skip(f"Could not load {bin_stop_path}")
        mod = importlib.util.module_from_spec(spec)
        # bin/stop imports `from client import send_ipc_request, SOCKET_PATH`
        # which only works when daemon dir is on sys.path.
        sys.path.insert(0, str(DAEMON_DIR))
        try:
            spec.loader.exec_module(mod)
        finally:
            # Don't pollute other tests
            if str(DAEMON_DIR) in sys.path:
                sys.path.remove(str(DAEMON_DIR))
        return mod

    def test_status_when_no_daemon(self, capsys, bin_stop_module):
        # When SOCKET_PATH doesn't exist, --status prints warning and exits 0
        with patch.object(bin_stop_module, "SOCKET_PATH", SOCKET_PATH):
            assert bin_stop_module.cmd_status() == 0
            captured = capsys.readouterr()
            assert "not running" in captured.out.lower() or "stopped" in captured.out.lower()

    def test_status_when_daemon_running(self, capsys, bin_stop_module):
        # Create the socket file so cmd_status doesn't short-circuit on "no UDS"
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
        SOCKET_PATH.touch()
        try:
            with patch.object(bin_stop_module, "SOCKET_PATH", SOCKET_PATH), \
                 patch.object(bin_stop_module, "send_ipc_request") as mock_send:
                mock_send.return_value = {
                    "status": "success",
                    "state": "running",
                    "active_tasks": ["task_1"],
                    "socket_path": str(SOCKET_PATH),
                }
                assert bin_stop_module.cmd_status() == 0
                captured = capsys.readouterr()
                assert "running" in captured.out.lower()
                assert "task_1" in captured.out
        finally:
            if SOCKET_PATH.exists():
                SOCKET_PATH.unlink()

    def test_stop_falls_back_to_file_on_ipc_error(self, capsys, bin_stop_module):
        fallback = TEST_ROOT / "STOP"
        with patch.object(bin_stop_module, "SOCKET_PATH", Path("/nonexistent.sock")), \
             patch.object(bin_stop_module, "FALLBACK_STOP_FILE", fallback):
            assert bin_stop_module.cmd_stop("test reason") == 0
            captured = capsys.readouterr()
            assert "fallback" in captured.out.lower()
            assert fallback.exists()
            content = fallback.read_text(encoding="utf-8")
            assert "test reason" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
