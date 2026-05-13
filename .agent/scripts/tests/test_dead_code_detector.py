#!/usr/bin/env python3
import unittest
import shutil
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

import analysis.dead_code_detector as dead_code_detector

class TestDeadCodeDetector(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_dead_code"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Create dummy structure
        (self.test_root / ".agent" / "scripts").mkdir(parents=True)
        (self.test_root / ".agent" / "agents").mkdir(parents=True)
        (self.test_root / ".agent" / "bus").mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('analysis.dead_code_detector.subprocess.run')
    @patch('analysis.dead_code_detector.Path.rglob')
    def test_find_unused_scripts(self, mock_rglob, mock_run):
        # Setup scripts
        script1 = MagicMock(spec=Path)
        script1.name = "used_script.py"
        script1.resolve.return_value = self.test_root / ".agent/scripts/used_script.py"
        
        script2 = MagicMock(spec=Path)
        script2.name = "dead_script.py"
        script2.resolve.return_value = self.test_root / ".agent/scripts/dead_script.py"
        
        mock_rglob.side_effect = [
            [script1, script2], # scripts_dir.rglob("*.py")
            []                  # skills_dir.rglob("*.py")
        ]
        
        # Setup grep results
        def mock_grep(cmd, capture_output, text):
            # cmd is ["grep", "-r", name, sdir]
            name = cmd[2]
            if name == "used_script.py":
                return MagicMock(stdout=".agent/agents/coder.md: reference to used_script.py\n")
            return MagicMock(stdout="")
            
        mock_run.side_effect = mock_grep
        
        with patch('analysis.dead_code_detector.Path.exists', return_value=True):
            unused = dead_code_detector.find_unused_scripts()
            
            self.assertEqual(len(unused), 1)
            self.assertEqual(unused[0].name, "dead_script.py")

if __name__ == "__main__":
    unittest.main()
