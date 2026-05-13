#!/usr/bin/env python3
import unittest
import sys
import shutil
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

import dev.checklist as checklist

class TestChecklistCore(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_checklist"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.patch_repo = patch('dev.checklist.REPO_ROOT', self.test_root)
        self.patch_repo.start()

    def tearDown(self):
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_check_script_coverage(self):
        # Setup mock scripts and tests
        script_dir = self.test_root / ".agent" / "scripts" / "mock_domain"
        script_dir.mkdir(parents=True)
        test_dir = self.test_root / ".agent" / "scripts" / "tests"
        test_dir.mkdir(parents=True)
        
        (script_dir / "script1.py").write_text("")
        (script_dir / "script2.py").write_text("")
        (test_dir / "test_script1.py").write_text("")
        
        # Should fail for script2
        ok, msg = checklist.check_script_coverage("mock_domain")
        self.assertFalse(ok)
        self.assertIn("script2.py", msg)
        
        # Should pass if we only check script1
        ok, msg = checklist.check_script_coverage("mock_domain", critical_only=["script1.py"])
        self.assertTrue(ok)

    @patch('dev.checklist.load_json_safe')
    @patch('dev.checklist.validate_json')
    @patch('dev.checklist.WATCHDOG_RULES_PATH')
    def test_check_watchdog_schema(self, mock_path, mock_validate, mock_load):
        mock_path.exists.return_value = True
        mock_load.return_value = {"rules": []}
        mock_validate.return_value = (True, "Valid")
        
        ok, msg = checklist.check_watchdog_schema()
        self.assertTrue(ok)
        self.assertEqual(msg, "Valid")

    @patch('dev.checklist.WATCHDOG_RULES_PATH')
    def test_run_fix(self, mock_watch):
        # We need actual Path objects for run_fix to call .mkdir() on them
        mock_watch.exists.return_value = False
        
        with patch('dev.checklist.print_header'), \
             patch('dev.checklist.print_step'), \
             patch('dev.checklist.print_success'), \
             patch('dev.checklist.print_warning'), \
             patch('lib.paths.AGENT_DIR', self.test_root / "agent"), \
             patch('lib.paths.BUS_DIR', self.test_root / "bus"), \
             patch('lib.paths.CONFIG_DIR', self.test_root / "config"), \
             patch('lib.paths.RULES_DIR', self.test_root / "rules"), \
             patch('lib.paths.SCRIPTS_DIR', self.test_root / "scripts"):
            checklist.run_fix()
            
        # Verify that it created directories
        self.assertTrue((self.test_root / "agent").exists())
        self.assertTrue((self.test_root / "bus").exists())

if __name__ == "__main__":
    unittest.main()
