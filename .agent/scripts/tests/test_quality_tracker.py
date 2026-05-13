#!/usr/bin/env python3
import unittest
import shutil
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

import analysis.quality_tracker as quality_tracker

class TestQualityTracker(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_quality"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.data_dir = self.test_root / ".agent" / "data"
        self.data_dir.mkdir(parents=True)
        
        self.patcher_repo = patch('analysis.quality_tracker.REPO_ROOT', self.test_root)
        self.patcher_data = patch('analysis.quality_tracker.DATA_DIR', self.data_dir)
        self.patcher_repo.start()
        self.patcher_data.start()

    def tearDown(self):
        self.patcher_repo.stop()
        self.patcher_data.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_record_event(self):
        args = MagicMock()
        args.repo = "owner/repo"
        args.pr = "1"
        args.action = "closed"
        args.merged = "true"
        args.labels = json.dumps(["agent-generated", "agent:excellent", "agent:coder"])
        
        quality_tracker.record_event(args)
        
        log_file = self.data_dir / "owner_repo" / "pr-quality.jsonl"
        self.assertTrue(log_file.exists())
        
        event = json.loads(log_file.read_text().strip())
        self.assertEqual(event["agent"], "coder")
        self.assertEqual(event["quality"], "agent:excellent")
        self.assertTrue(event["merged"])

    def test_load_log(self):
        repo_dir = self.data_dir / "repo1"
        repo_dir.mkdir()
        log_file = repo_dir / "pr-quality.jsonl"
        log_file.write_text(json.dumps({"agent": "a1", "quality": "agent:ok"}) + "\n")
        
        events = quality_tracker.load_log()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent"], "a1")

    def test_build_report(self):
        events = [
            {"action": "closed", "agent": "coder", "quality": "agent:excellent", "merged": True},
            {"action": "closed", "agent": "coder", "quality": "agent:ok", "merged": True},
            {"action": "closed", "agent": "debugger", "quality": "agent:rejected", "merged": False}
        ]
        
        report = quality_tracker.build_report(events, "owner/repo")
        
        self.assertIn("# Agent Quality Scores", report)
        self.assertIn("`coder`", report)
        self.assertIn("`debugger`", report)
        # Average for coder: (5 + 4) / 2 = 4.5
        self.assertIn("**4.5**", report)
        # Average for debugger: 0 / 1 = 0
        self.assertIn("**0.0**", report)

if __name__ == "__main__":
    unittest.main()
