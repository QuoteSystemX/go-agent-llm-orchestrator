#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import os
import shutil
import json
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.dead_code_detector; import sys; sys.modules['dead_code_detector'] = sys.modules['analysis.dead_code_detector']; import analysis.dead_code_detector as dead_code_detector

class TestDeadCodeDetector(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_dead_code"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Create dummy structure
        os.makedirs(".agent/scripts", exist_ok=True)
        os.makedirs(".agent/agents", exist_ok=True)
        
        self.script_a = Path(".agent/scripts/used_script.py")
        self.script_a.write_text("print('used')")
        
        self.script_b = Path(".agent/scripts/unused_script.py")
        self.script_b.write_text("print('unused')")
        
        self.agent_file = Path(".agent/agents/my_agent.md")
        self.agent_file.write_text("I use used_script.py")

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch("subprocess.run")
    def test_find_unused_scripts(self, mock_grep):
        def side_effect(args, **kwargs):
            query = args[2]
            target_dir = args[3]
            mock_res = MagicMock()
            if query == "used_script.py" and target_dir == ".agent/agents":
                mock_res.stdout = ".agent/agents/my_agent.md: I use used_script.py"
            else:
                mock_res.stdout = ""
            return mock_res
            
        mock_grep.side_effect = side_effect
        
        unused = dead_code_detector.find_unused_scripts()
        
        unused_names = [s.name for s in unused]
        self.assertIn("unused_script.py", unused_names)
        self.assertNotIn("used_script.py", unused_names)

if __name__ == "__main__":
    unittest.main()
