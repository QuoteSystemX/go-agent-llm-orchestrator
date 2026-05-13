#!/usr/bin/env python3
import unittest
import sys
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import os
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import delivery.sync_parity_collector as spc

class TestSyncParityCollector(unittest.TestCase):
    @patch('subprocess.run')
    def test_run_drift_detected(self, mock_run):
        # Patch TARGETS inside the module where it's imported
        with patch('sync_agents.TARGETS', {"agent1": {}, "agent2": {}}):
            # agent1 is OK, agent2 has drift
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Target agent1 is in sync"),
                MagicMock(returncode=1, stdout="Drift: .agent/rules/agent2.md is stale\nMissing: .agent/skills/agent2/script.py")
            ]
            
            collector = spc.SyncParityCollector()
            with patch.object(collector, 'save', return_value=None):
                collector.run()
                
            metrics = collector.data["metrics"]["targets"]["value"]
            self.assertEqual(metrics["agent1"]["status"], "OK")
            self.assertEqual(metrics["agent2"]["status"], "DRIFT")
            self.assertEqual(len(metrics["agent2"]["issues"]), 2)
            self.assertEqual(collector.data["metrics"]["targets"]["status"], "WARN")

    @patch('subprocess.run')
    def test_run_all_ok(self, mock_run):
        with patch('sync_agents.TARGETS', {"agent1": {}}):
            mock_run.return_value = MagicMock(returncode=0, stdout="OK")
            
            collector = spc.SyncParityCollector()
            with patch.object(collector, 'save', return_value=None):
                collector.run()
                
            self.assertEqual(collector.data["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
