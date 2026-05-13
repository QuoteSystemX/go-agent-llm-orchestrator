#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import models.profile_routing as profile

class TestProfileRouting(unittest.TestCase):
    def test_measure_step(self):
        def dummy_func():
            return "result"
        
        with patch('sys.stdout', new=MagicMock()):
            result, elapsed = profile.measure_step("test", dummy_func)
            
        self.assertEqual(result, "result")
        self.assertGreaterEqual(elapsed, 0)

    @patch('subprocess.run')
    def test_profile_task(self, mock_run):
        # Mock the subprocess calls
        def side_effect(*args, **kwargs):
            mock_proc = MagicMock()
            cmd = args[0]
            if "model_router.py" in cmd:
                mock_proc.stdout = json.dumps({"tier": "L1", "model_id": "model1", "provider": "ollama"})
                mock_proc.returncode = 0
            elif "status_report.py" in cmd:
                mock_proc.returncode = 0
            elif "conflict_resolver.py" in cmd:
                mock_proc.returncode = 0
            elif "curl" in cmd:
                mock_proc.stdout = "models"
                mock_proc.returncode = 0
            else:
                mock_proc.stdout = ""
                mock_proc.returncode = 0
            return mock_proc
            
        mock_run.side_effect = side_effect
        
        with patch('sys.stdout', new=MagicMock()):
            result = profile.profile_task("test task", "L1")
            
        self.assertEqual(result["tier"], "L1")
        self.assertEqual(result["decided_tier"], "L1")
        self.assertEqual(result["model"], "model1")
        self.assertEqual(result["provider"], "ollama")
        
        # Verify step timings exist
        self.assertIn("router", result["steps"])
        self.assertIn("health", result["steps"])
        self.assertIn("conflict", result["steps"])

    @patch('models.profile_routing.profile_task')
    def test_main(self, mock_profile):
        mock_profile.return_value = {
            "task": "task",
            "tier": "L1",
            "total_ms": 100.0,
            "steps": {"router": 50.0}
        }
        
        with patch('sys.stdout', new=MagicMock()):
            profile.main()
            
        self.assertEqual(mock_profile.call_count, 4)

if __name__ == "__main__":
    unittest.main()
