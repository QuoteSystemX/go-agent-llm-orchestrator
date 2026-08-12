#!/usr/bin/env python3
import unittest
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.war_room_manager as war_room_manager

class TestWarRoomManager(unittest.TestCase):
    @patch('orchestration.war_room_manager._activate_git_ops')
    @patch('orchestration.war_room_manager.bus_manager')
    @patch('time.sleep', return_value=None)
    def test_manage_war_room_success(self, mock_sleep, mock_bus, mock_git_ops):
        # _activate_git_ops does real `git checkout -b` / `git commit` when not
        # mocked — regression coverage for a real incident where running this
        # test suite left stray fix/inc-* branches (with real commits!) in the
        # repo. Never let this test touch git for real.
        mock_git_ops.return_value = {"branch": "fix/inc-inc_123", "status": "committed"}

        # 1. Setup mock incident
        incident_id = "inc_123"
        mock_bus.wait_for_object.return_value = {
            "id": incident_id,
            "content": {"stderr": "Panic: memory leak"}
        }

        # 2. Run manager
        war_room_manager.manage_war_room(incident_id)

        # 3. Verify interactions
        # Should push debug task
        debug_call = mock_bus.push.call_args_list[0]
        self.assertEqual(debug_call.args[0], f"task_debug_{incident_id}")
        self.assertIn("debugger", debug_call.args[3])

        # Should push fix task
        fix_call = mock_bus.push.call_args_list[1]
        self.assertEqual(fix_call.args[0], f"task_fix_{incident_id}")
        self.assertIn("test-engineer", fix_call.args[3])

        # Should push proposed fix
        final_call = mock_bus.push.call_args_list[2]
        self.assertEqual(final_call.args[0], f"fix_{incident_id}")
        self.assertEqual(final_call.args[1], "proposed_fix")

        # Git-Ops was invoked exactly once, and never for real, with the
        # incident id and the fix it needs to write the durable log itself
        mock_git_ops.assert_called_once()
        self.assertEqual(mock_git_ops.call_args.args[0], incident_id)
        self.assertEqual(mock_git_ops.call_args.args[2], json.loads(final_call.args[3]))

    @patch('orchestration.war_room_manager.bus_manager')
    def test_manage_war_room_not_found(self, mock_bus):
        mock_bus.wait_for_object.return_value = None

        # Should exit gracefully
        war_room_manager.manage_war_room("missing")
        self.assertEqual(mock_bus.push.call_count, 0)

    @patch('orchestration.war_room_manager._report_pr')
    @patch('orchestration.war_room_manager._commit_fix')
    @patch('orchestration.war_room_manager._log_incident')
    @patch('orchestration.war_room_manager._run_validation', return_value=True)
    @patch('orchestration.war_room_manager._create_branch', return_value="fix/inc-inc_9")
    def test_activate_git_ops_logs_before_commit(
        self, mock_branch, mock_validate, mock_log, mock_commit, mock_report,
    ):
        # The incident record must be staged (written) before _commit_fix's
        # `git add -A` runs, or it never lands in the fix's commit.
        call_order = []
        mock_log.side_effect = lambda *a, **k: call_order.append("log")
        mock_commit.side_effect = lambda *a, **k: call_order.append("commit") or True

        diagnosis = {"root_cause_signature": "missing-timeout-default"}
        fix = {"incident_ref": "inc_9"}
        status = war_room_manager._activate_git_ops("inc_9", diagnosis, fix)

        self.assertEqual(call_order, ["log", "commit"])
        mock_log.assert_called_once_with(
            "inc_9", diagnosis, fix, {"branch": "fix/inc-inc_9", "status": "committed"},
        )
        self.assertEqual(status, {"branch": "fix/inc-inc_9", "status": "committed"})

    @patch('orchestration.war_room_manager._log_incident')
    @patch('orchestration.war_room_manager._run_validation', return_value=False)
    @patch('orchestration.war_room_manager._create_branch', return_value="fix/inc-inc_9")
    def test_activate_git_ops_skips_log_on_checklist_failure(
        self, mock_branch, mock_validate, mock_log,
    ):
        status = war_room_manager._activate_git_ops("inc_9", None, {"incident_ref": "inc_9"})
        mock_log.assert_not_called()
        self.assertEqual(status["status"], "checklist_failed")


class TestLogIncident(unittest.TestCase):
    """_log_incident writes the durable record blameless_retro.py reads."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.log_path = Path(self.tmp_dir) / "incidents.jsonl"
        self.patch_log = patch('orchestration.war_room_manager.INCIDENTS_LOG', self.log_path)
        self.patch_log.start()

    def tearDown(self):
        self.patch_log.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _read_record(self):
        lines = self.log_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        return json.loads(lines[0])

    def test_unwraps_raw_content_dicts(self):
        war_room_manager._log_incident(
            "inc_1",
            {"root_cause_signature": "missing-timeout-default", "summary": "diag"},
            {"summary": "fix summary"},
            {"branch": "fix/inc-inc_1", "status": "committed"},
        )
        record = self._read_record()
        self.assertEqual(record["incident_id"], "inc_1")
        self.assertEqual(record["root_cause_signature"], "missing-timeout-default")
        self.assertEqual(record["diagnosis_summary"], "diag")
        self.assertEqual(record["fix_summary"], "fix summary")
        self.assertEqual(record["branch"], "fix/inc-inc_1")
        self.assertEqual(record["status"], "committed")

    def test_unwraps_full_bus_objects(self):
        war_room_manager._log_incident(
            "inc_2",
            {"id": "diagnosis_inc_2", "content": {"root_cause_signature": "race-condition"}},
            {"id": "fix_inc_2", "content": {"status": "ready_to_apply"}},
            {"branch": "fix/inc-inc_2", "status": "no_changes"},
        )
        record = self._read_record()
        self.assertEqual(record["root_cause_signature"], "race-condition")
        self.assertEqual(record["fix_summary"], "ready_to_apply")

    def test_missing_diagnosis_defaults_to_unknown(self):
        war_room_manager._log_incident(
            "inc_3", None, {"status": "ready_to_apply"},
            {"branch": "fix/inc-inc_3", "status": "committed"},
        )
        record = self._read_record()
        self.assertEqual(record["root_cause_signature"], "unknown")


if __name__ == "__main__":
    unittest.main()
