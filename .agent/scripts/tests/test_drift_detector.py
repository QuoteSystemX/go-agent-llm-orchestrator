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

import health.drift_detector as drift_detector

class TestDriftDetector(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_drift"
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.arch_file = self.test_root / ".agent" / "ARCHITECTURE.md"
        self.arch_file.parent.mkdir(parents=True)
        
        self.patcher = patch('health.drift_detector.REPO_ROOT', self.test_root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root)

    def test_check_arch_consistency_agent_drift(self):
        # Create ARCHITECTURE.md listing an agent that doesn't exist
        self.arch_file.write_text("## Agents\n| `missing-agent` | info |")
        
        drifts = drift_detector.check_arch_consistency()
        self.assertTrue(any("AGENT DRIFT: 'missing-agent'" in d for d in drifts))
        
        # Create the agent file
        agent_dir = self.test_root / ".agent" / "agents"
        agent_dir.mkdir(parents=True)
        (agent_dir / "missing-agent.md").write_text("info")
        
        drifts = drift_detector.check_arch_consistency()
        self.assertEqual(len(drifts), 0)

    def test_check_arch_consistency_skill_drift(self):
        self.arch_file.write_text("## Skills\n| `missing-skill` | info |")
        
        drifts = drift_detector.check_arch_consistency()
        self.assertTrue(any("SKILL DRIFT: 'missing-skill'" in d for d in drifts))
        
        # Create the skill dir
        skill_dir = self.test_root / ".agent" / "skills" / "missing-skill"
        skill_dir.mkdir(parents=True)
        
        drifts = drift_detector.check_arch_consistency()
        self.assertEqual(len(drifts), 0)

    @patch('health.drift_detector.get_git_changes')
    def test_detect_drift_file(self, mock_changes):
        mock_changes.return_value = ["src/new_logic.py"]
        
        # Create empty docs
        self.arch_file.write_text("## Intro\nGeneric documentation content.")
        
        drifts = drift_detector.detect_drift()
        self.assertTrue(any("FILE DRIFT: src/new_logic.py" in d for d in drifts))
        
        # Add to docs
        self.arch_file.write_text("## Intro\nMentions new_logic.py")
        drifts = drift_detector.detect_drift()
        self.assertEqual(len(drifts), 0)

    @patch('health.drift_detector.get_documented_files')
    def test_close_resolved_cards(self, mock_docs):
        # A file that no longer exists → its drift card must be closed.
        # A file that still exists AND is undocumented → card must stay open.
        mock_docs.return_value = "Some docs without those files"

        tasks_dir = self.test_root / "tasks"
        tasks_dir.mkdir(parents=True)

        # Card 1: drift gone — file no longer exists
        (tasks_dir / "2026-08-01-fix-doc-drift-gone-deadbeef.md").write_text(
            "# [CHORE] Fix doc drift: FILE DRIFT: src/removed_thing.py (modified but not in docs)\n\n## Problem\n"
        )
        # Card 2: drift still active — file exists and is undocumented
        (self.test_root / "src").mkdir(parents=True)
        (self.test_root / "src" / "active_thing.py").write_text("x = 1")
        (tasks_dir / "2026-08-02-fix-doc-drift-active-deadbeef.md").write_text(
            "# [CHORE] Fix doc drift: FILE DRIFT: src/active_thing.py (modified but not in docs)\n\n## Problem\n"
        )

        actions = drift_detector.close_resolved_cards()
        self.assertEqual(len(actions), 1)
        self.assertIn("gone-deadbeef", actions[0])

        # Resolved card moved to done/, active one untouched
        self.assertFalse((tasks_dir / "2026-08-01-fix-doc-drift-gone-deadbeef.md").exists())
        self.assertTrue((tasks_dir / "done" / "2026-08-01-fix-doc-drift-gone-deadbeef.md").exists())
        self.assertTrue((tasks_dir / "2026-08-02-fix-doc-drift-active-deadbeef.md").exists())

        # Closed card carries a Resolution section
        closed = (tasks_dir / "done" / "2026-08-01-fix-doc-drift-gone-deadbeef.md").read_text()
        self.assertIn("## Resolution", closed)
        self.assertIn("CLOSED", closed)

        # Second run: nothing more to close
        actions = drift_detector.close_resolved_cards()
        self.assertEqual(len(actions), 0)

if __name__ == "__main__":
    unittest.main()
