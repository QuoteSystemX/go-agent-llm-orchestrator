#!/usr/bin/env python3
import unittest
import json
import sys
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
    @patch('orchestration.war_room_manager.bus_manager')
    @patch('time.sleep', return_value=None)
    def test_manage_war_room_success(self, mock_sleep, mock_bus):
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

    @patch('orchestration.war_room_manager.bus_manager')
    def test_manage_war_room_not_found(self, mock_bus):
        mock_bus.wait_for_object.return_value = None
        
        # Should exit gracefully
        war_room_manager.manage_war_room("missing")
        self.assertEqual(mock_bus.push.call_count, 0)

if __name__ == "__main__":
    unittest.main()
