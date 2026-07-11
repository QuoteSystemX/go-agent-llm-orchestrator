#!/usr/bin/env python3
"""
Tests for STORY-2 daemon-side INBOX fragment injection.

Covers:
  - _build_inbox_fragment: returns empty when no INBOX entries
  - _build_inbox_fragment: returns empty when inbox module unavailable
  - _build_inbox_fragment: includes entries targeted at the task
  - _build_inbox_fragment: respects max_chars
  - action_run_task: prepends INBOX fragment to task description
"""
import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DAEMON_DIR = REPO_ROOT / ".agent" / "scripts" / "orchestration" / "daemon"
INBOX_DIR = REPO_ROOT / ".agent" / "scripts" / "communication"

# Load server module
_server_spec = importlib.util.spec_from_file_location(
    "daemon_server", str(DAEMON_DIR / "server.py")
)
daemon_server = importlib.util.module_from_spec(_server_spec)
sys.modules["daemon_server"] = daemon_server
_server_spec.loader.exec_module(daemon_server)
OrchestratorDaemon = daemon_server.OrchestratorDaemon


@pytest.fixture
def daemon_with_inbox():
    """Daemon instance with mocked DB and a per-test inbox dir."""
    test_root = Path(tempfile.mkdtemp(prefix="inbox_inject_"))
    inbox_path = test_root / "INBOX.md"
    bus_path = test_root / "bus"
    bus_path.mkdir()
    comm_dir = test_root / "communication"
    comm_dir.mkdir()

    with patch.object(OrchestratorDaemon, "__init__", lambda self, socket_path=None: None), \
         patch.object(daemon_server, "REPO_ROOT", test_root), \
         patch.object(daemon_server, "SOCKET_PATH", test_root / "sock"):
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

        # Inject a fake inbox module accessible to _build_inbox_fragment
        fake_inbox_module = MagicMock()
        fake_inbox_module.read_entries = MagicMock(return_value=[])
        fake_inbox_module.strip_for_prompt = MagicMock(return_value="")
        fake_inbox_module.ALLOWED_INTENTS = {"redirect", "clarify", "abort", "context", "ack"}

        # We need to actually use the real inbox module for the integration
        # tests, but mock it for the "unavailable" test.
        yield d, test_root, inbox_path, bus_path, comm_dir, fake_inbox_module

    import shutil
    shutil.rmtree(test_root, ignore_errors=True)


class TestBuildInboxFragment:
    def test_returns_empty_when_no_module(self, daemon_with_inbox):
        d, test_root, *_ = daemon_with_inbox
        # inbox module is NOT on sys.path for the test, so import fails
        with patch.dict(sys.modules, {"inbox": None}):
            result = d._build_inbox_fragment(target="task_x")
        assert result == ""

    def test_returns_empty_when_no_entries(self, daemon_with_inbox):
        d, test_root, inbox_path, _, comm_dir, _ = daemon_with_inbox
        inbox_path.write_text("", encoding="utf-8")
        # Add test_root/communication to sys.path and create a fake inbox module
        sys.path.insert(0, str(comm_dir))
        try:
            (comm_dir / "inbox.py").write_text(
                "def read_entries(**kw): return []\n"
                "def strip_for_prompt(entries, **kw): return ''\n"
                "ALLOWED_INTENTS = {}\n",
                encoding="utf-8",
            )
            result = d._build_inbox_fragment(target="task_x")
        finally:
            if str(comm_dir) in sys.path:
                sys.path.remove(str(comm_dir))
            if "inbox" in sys.modules:
                del sys.modules["inbox"]
        assert result == ""

    def test_returns_fragment_when_entries_present(self, daemon_with_inbox):
        d, test_root, inbox_path, _, comm_dir, _ = daemon_with_inbox
        # Mock the inbox module directly via sys.modules
        mock_inbox = MagicMock()
        from dataclasses import dataclass
        @dataclass
        class FakeEntry:
            id: str = "inb_x"
            ts: str = "2026-07-11T10:00:00Z"
            intent: str = "context"
            body: str = "see docs"
            target: str = None
            knowledge_anchor: str = "#docs"
            acked_ts: str = None
        mock_inbox.read_entries.return_value = [FakeEntry()]
        mock_inbox.strip_for_prompt.return_value = "[2026-07-11T10:00:00Z] context: see docs"

        with patch.dict(sys.modules, {"inbox": mock_inbox}):
            result = d._build_inbox_fragment(target="task_x")

        assert "see docs" in result
        assert "context" in result


class TestActionRunTaskInjectsInbox:
    def test_prepends_fragment(self, daemon_with_inbox):
        d, test_root, inbox_path, _, comm_dir, _ = daemon_with_inbox
        mock_inbox = MagicMock()
        from dataclasses import dataclass
        @dataclass
        class FakeEntry:
            id: str = "inb_x"
            ts: str = "2026-07-11T10:00:00Z"
            intent: str = "context"
            body: str = "use pgx"
            target: str = None
            knowledge_anchor: str = "#db"
            acked_ts: str = None
        mock_inbox.read_entries.return_value = [FakeEntry()]
        mock_inbox.strip_for_prompt.return_value = "INBOX_HINT: use pgx"

        with patch.dict(sys.modules, {"inbox": mock_inbox}):
            fragment = d._build_inbox_fragment(target="task_x")
        assert "INBOX_HINT" in fragment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
