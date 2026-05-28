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
    def test_find_unused_scripts(self, mock_run):
        """Verify that scripts with no grep references are reported as unused."""
        # Build two script Path objects rooted in the test temp dir
        scripts_base = self.test_root / ".agent" / "scripts"
        used_script  = scripts_base / "used_script.py"
        dead_script  = scripts_base / "dead_script.py"
        used_script.write_text("# used")
        dead_script.write_text("# dead")

        def mock_grep(cmd, capture_output, text):
            # cmd = ["grep", "-E", "-r", pattern, sdir]
            pattern = cmd[3] if len(cmd) > 3 else ""
            if "used_script" in pattern:
                # Simulate a reference found in a different file (agents/coder.md)
                ref_path = str(self.test_root / ".agent/agents/coder.md")
                return MagicMock(stdout=f"{ref_path}: reference to used_script\n")
            return MagicMock(stdout="")

        mock_run.side_effect = mock_grep

        # Patch rglob so only our 2 scripts are scanned, skills dir returns empty
        original_rglob = Path.rglob

        def fake_rglob(self_path, pattern):
            path_str = str(self_path)
            if "skills" in path_str:
                return iter([])
            if "scripts" in path_str and pattern == "*.py":
                return iter([used_script, dead_script])
            return original_rglob(self_path, pattern)

        with patch.object(Path, 'rglob', fake_rglob):
            # Make all search dirs appear to exist so grep is attempted
            with patch.object(Path, 'exists', return_value=True):
                unused = dead_code_detector.find_unused_scripts()

        unused_names = [u.name for u in unused]
        self.assertIn("dead_script.py", unused_names, f"Expected dead_script.py in unused. Got: {unused_names}")
        self.assertNotIn("used_script.py", unused_names, f"used_script.py must NOT be in unused. Got: {unused_names}")


if __name__ == "__main__":
    unittest.main()
