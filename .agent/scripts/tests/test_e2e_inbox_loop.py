#!/usr/bin/env python3
"""
E2E tests for STORY-2 + STORY-6 (C5).

These tests exercise the FULL FLOW end-to-end:
  1. Human appends an INBOX entry via `inbox.append_entry()`
  2. Daemon's `action_run_task` is invoked
  3. Daemon's `_build_inbox_fragment()` reads the entry
  4. Fragment is prepended to the task description
  5. The same entry, once acked, is NOT re-injected

This is the smallest possible test that proves the loop is closed.
It's not a "real" e2e (we don't start an actual subprocess daemon),
but it covers the full data flow through the modules.

Run:
    python3 -m pytest .agent/scripts/tests/test_e2e_inbox_loop.py -v
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
COMM_DIR = REPO_ROOT / ".agent" / "scripts" / "communication"
PERM_DIR = REPO_ROOT / ".agent" / "scripts" / "permissions"

# Load inbox module
_inbox_spec = importlib.util.spec_from_file_location(
    "inbox_under_test", str(COMM_DIR / "inbox.py")
)
inbox_mod = importlib.util.module_from_spec(_inbox_spec)
sys.modules["inbox_under_test"] = _inbox_spec.loader
_inbox_spec.loader.exec_module(inbox_mod)

# Load daemon_server module
_daemon_spec = importlib.util.spec_from_file_location(
    "daemon_server_under_test", str(DAEMON_DIR / "server.py")
)
daemon_mod = importlib.util.module_from_spec(_daemon_spec)
sys.modules["daemon_server_under_test"] = _daemon_spec.loader
_daemon_spec.loader.exec_module(daemon_mod)
OrchestratorDaemon = daemon_mod.OrchestratorDaemon


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    """Set up a fully isolated e2e environment with INBOX + daemon."""
    # 1. Setup INBOX in a temp dir
    inbox_path = tmp_path / "INBOX.md"
    bus_path = tmp_path / "bus"
    bus_path.mkdir()
    cap_yaml = tmp_path / "capabilities.yaml"
    cap_yaml.write_text("""
version: "1.0.0"
roles:
  infra-agent:
    capabilities:
      - { cap: modify-tasks, scope: global }
      - { cap: stop-daemon, scope: global }
  squad-agent:
    capabilities: []
  session-agent:
    capabilities: []
  human:
    capabilities: []
operations:
  run_task: modify-tasks
  stop: stop-daemon
""", encoding="utf-8")

    # 2. Patch inbox_mod to use temp INBOX_PATH
    monkeypatch.setattr(inbox_mod, "INBOX_PATH", inbox_path)
    monkeypatch.setattr(inbox_mod, "REPO_ROOT", tmp_path)

    # 3. Patch daemon_mod to use temp REPO_ROOT
    monkeypatch.setattr(daemon_mod, "REPO_ROOT", tmp_path)

    # 4. Patch capability_check (loaded by daemon at runtime)
    sys.path.insert(0, str(PERM_DIR))
    cap_spec = importlib.util.spec_from_file_location(
        "capability_check_under_test", str(PERM_DIR / "capability_check.py")
    )
    cap_mod = importlib.util.module_from_spec(cap_spec)
    sys.modules["capability_check_under_test"] = cap_mod
    cap_spec.loader.exec_module(cap_mod)
    cap_mod.MATRIX_PATH = cap_yaml
    cap_mod.REPO_ROOT = tmp_path
    # Critical: register the canonical 'capability_check' name so that
    # `from capability_check import ...` inside daemon/server.py picks up
    # our patched module.
    sys.modules["capability_check"] = cap_mod

    # Same trick for inbox: server.py does `from inbox import ...`
    sys.path.insert(0, str(COMM_DIR))
    sys.modules["inbox"] = inbox_mod

    # 5. Set up daemon instance
    with patch.object(OrchestratorDaemon, "__init__", lambda self, socket_path=None: None):
        daemon = OrchestratorDaemon(socket_path=tmp_path / "sock")
        daemon.socket_path = tmp_path / "sock"
        daemon.graph = MagicMock()
        daemon.db = MagicMock()
        daemon.active_tasks = {}
        daemon.subscribers = {}
        daemon.shutting_down = False
        daemon.server = None

        async def _noop_shutdown(sig):
            pass
        daemon.shutdown = _noop_shutdown

    yield {
        "tmp_path": tmp_path,
        "inbox_path": inbox_path,
        "bus_path": bus_path,
        "cap_yaml": cap_yaml,
        "daemon": daemon,
        "inbox": inbox_mod,
    }

    import shutil
    shutil.rmtree(tmp_path, ignore_errors=True)


class TestInboxToTaskInjection:
    """E2E: human sends INBOX → daemon injects into task description."""

    def test_redirect_entry_injected_into_task(self, e2e_env):
        # Step 1: Human sends INBOX entry
        entry = e2e_env["inbox"].append_entry(
            intent="redirect",
            body="use pgx for PostgreSQL",
            knowledge_anchor="#postgres",
        )
        assert entry.id.startswith("inb_")
        assert e2e_env["inbox_path"].exists()

        # Step 2: Daemon's _build_inbox_fragment reads the entry
        fragment = e2e_env["daemon"]._build_inbox_fragment(target="task_xyz")
        assert "use pgx for PostgreSQL" in fragment
        assert "anchor: #postgres" in fragment
        assert "redirect" in fragment

    def test_context_entry_injected(self, e2e_env):
        entry = e2e_env["inbox"].append_entry(
            intent="context",
            body="see auth policy for JWT requirements",
            knowledge_anchor="#auth",
        )
        fragment = e2e_env["daemon"]._build_inbox_fragment(target="task_abc")
        assert "see auth policy" in fragment
        assert "#auth" in fragment

    def test_acked_entry_not_injected(self, e2e_env):
        # Send then ack
        entry = e2e_env["inbox"].append_entry(
            intent="clarify",
            body="what is the schema?",
        )
        # Before ack: in fragment
        fragment1 = e2e_env["daemon"]._build_inbox_fragment(target="task_1")
        assert "what is the schema?" in fragment1

        # After ack: NOT in fragment
        e2e_env["inbox"].ack_entry(entry.id)
        fragment2 = e2e_env["daemon"]._build_inbox_fragment(target="task_1")
        assert "what is the schema?" not in fragment2

    def test_target_filter_excludes_other_tasks(self, e2e_env):
        # Send entry targeted at task_abc
        e2e_env["inbox"].append_entry(
            intent="context",
            body="alpha specific note",
            target="task_abc",
            knowledge_anchor="#x",
        )
        # Send entry targeted at task_xyz
        e2e_env["inbox"].append_entry(
            intent="context",
            body="beta specific note",
            target="task_xyz",
            knowledge_anchor="#y",
        )
        # task_abc fragment only includes alpha entry
        frag_abc = e2e_env["daemon"]._build_inbox_fragment(target="task_abc")
        assert "alpha specific note" in frag_abc
        assert "beta specific note" not in frag_abc

        # task_xyz fragment only includes beta entry
        frag_xyz = e2e_env["daemon"]._build_inbox_fragment(target="task_xyz")
        assert "beta specific note" in frag_xyz
        assert "alpha specific note" not in frag_xyz

    def test_sanitization_removes_dangerous_chars(self, e2e_env):
        """E2E: body with markdown/HTML is sanitized before injection."""
        e2e_env["inbox"].append_entry(
            intent="context",
            body="see <script>alert(1)</script> and **bold** text",
            knowledge_anchor="#x",
        )
        fragment = e2e_env["daemon"]._build_inbox_fragment(target="task_1")
        # The body should be sanitized: no <>, no **, no backticks
        assert "<script>" not in fragment
        assert "**bold**" not in fragment
        # The plain text survives
        assert "see" in fragment
        assert "alert(1)" in fragment
        assert "bold" in fragment
        assert "text" in fragment

    def test_global_entries_visible_to_all_tasks(self, e2e_env):
        # Entry without target = visible globally
        e2e_env["inbox"].append_entry(
            intent="context",
            body="global note for all tasks",
            knowledge_anchor="#global",
        )
        # Should appear in every task's fragment
        for target in ["task_1", "task_2", "task_anything"]:
            frag = e2e_env["daemon"]._build_inbox_fragment(target=target)
            assert "global note for all tasks" in frag


class TestCapabilityDenialE2E:
    """E2E: cap check fires in daemon.handle_client for privileged actions."""

    def test_session_agent_run_task_denied(self, e2e_env):
        e2e_env["daemon"].db.acquire_lock.return_value = True

        async def runner():
            reader = asyncio.StreamReader()
            reader.feed_data(
                json.dumps({
                    "action": "run_task",
                    "task_id": "task_x",
                    "task": "do something",
                    "caller_role": "session-agent",  # explicitly passed
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

            await e2e_env["daemon"].handle_client(reader, writer)
            assert writer.write.called
            written = writer.write.call_args[0][0].decode()
            response = json.loads(written.strip())
            return response

        response = asyncio.run(runner())
        assert response["code"] == "CAPABILITY_DENIED"
        assert response["caller_role"] == "session-agent"


class TestFullE2EHappyPath:
    """E2E: realistic scenario — user redirects, daemon injects, agent acks."""

    def test_full_redirect_flow(self, e2e_env):
        # 1. User notices agent is using wrong tool
        # 2. User sends redirect via INBOX
        entry = e2e_env["inbox"].append_entry(
            intent="redirect",
            body="use the v2 API in src api v2, not src api",
            target="task_abc",
            knowledge_anchor="#api-versioning",
        )

        # 3. Next task starts
        fragment = e2e_env["daemon"]._build_inbox_fragment(target="task_abc")
        assert "use the v2 API" in fragment
        # Note: underscores and dots are stripped by sanitization
        assert "src api v2" in fragment

        # 4. Agent acts on it, acks
        acked = e2e_env["inbox"].ack_entry(entry.id)
        assert acked is True

        # 5. Fragment is empty for next task
        fragment_after = e2e_env["daemon"]._build_inbox_fragment(target="task_abc")
        assert "use the v2 API" not in fragment_after

        # 6. The file has the entry marked as acked
        content = e2e_env["inbox_path"].read_text(encoding="utf-8")
        assert '"acked_ts"' in content
        assert entry.id in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
