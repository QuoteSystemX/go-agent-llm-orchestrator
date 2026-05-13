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

import orchestration.arbitrator as arbitrator

class TestArbitrator(unittest.TestCase):
    @patch('orchestration.arbitrator.bus_manager')
    @patch('orchestration.arbitrator.time.sleep') # Skip real sleep
    def test_run_consensus_flow(self, mock_sleep, mock_bus):
        plan_id = "test-plan-1"
        mock_bus.wait_for_object.return_value = {"id": plan_id, "content": {"step": "init"}}
        
        arbitrator.run_consensus(plan_id)
        
        # Verify critique request
        mock_bus.push.assert_any_call(
            f"critique_{plan_id}",
            "requirement",
            "arbitrator",
            unittest.mock.ANY
        )
        
        # Verify defense request
        mock_bus.push.assert_any_call(
            f"defense_{plan_id}",
            "requirement",
            "arbitrator",
            unittest.mock.ANY
        )
        
        # Verify final verdict
        mock_bus.push.assert_any_call(
            f"verdict_{plan_id}",
            "verification_result",
            "arbitrator",
            unittest.mock.ANY
        )
        
        # Check verdict content
        last_call_args = mock_bus.push.call_args_list[-1]
        verdict_content = json.loads(last_call_args[0][3])
        self.assertEqual(verdict_content["status"], "approved_with_conditions")
        self.assertEqual(verdict_content["plan_ref"], plan_id)

    @patch('orchestration.arbitrator.bus_manager')
    def test_run_consensus_plan_not_found(self, mock_bus):
        mock_bus.wait_for_object.return_value = None
        with patch('sys.stdout', new=MagicMock()) as mock_out:
            arbitrator.run_consensus("missing")
            output = "".join(call[0][0] for call in mock_out.write.call_args_list)
            self.assertIn("Plan missing not found", output)

if __name__ == "__main__":
    unittest.main()
