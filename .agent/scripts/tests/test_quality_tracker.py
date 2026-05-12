#!/usr/bin/env python3
import unittest
import os
import shutil
import json
from pathlib import Path
import sys
import argparse

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.quality_tracker; import sys; sys.modules['quality_tracker'] = sys.modules['analysis.quality_tracker']; import analysis.quality_tracker as quality_tracker

class TestQualityTracker(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_quality"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override paths
        self.original_root = quality_tracker.REPO_ROOT
        self.original_data = quality_tracker.DATA_DIR
        quality_tracker.REPO_ROOT = self.test_root
        quality_tracker.DATA_DIR = self.test_root / ".agent" / "data"

    def tearDown(self):
        quality_tracker.REPO_ROOT = self.original_root
        quality_tracker.DATA_DIR = self.original_data
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_record_event(self):
        args = argparse.Namespace(
            record_event=True,
            pr="42",
            action="closed",
            merged="true",
            labels='["agent-generated","agent:ok","agent:debugger"]',
            repo="owner/repo",
            output=None
        )
        quality_tracker.record_event(args)
        
        log_file = quality_tracker.DATA_DIR / "owner_repo" / "pr-quality.jsonl"
        self.assertTrue(log_file.exists())
        
        with open(log_file) as f:
            event = json.loads(f.readline())
            self.assertEqual(event["pr"], "42")
            self.assertEqual(event["agent"], "debugger")
            self.assertEqual(event["quality"], "agent:ok")
            self.assertTrue(event["merged"])

    def test_build_report(self):
        events = [
            {"action": "closed", "agent": "debugger", "quality": "agent:excellent", "merged": True},
            {"action": "closed", "agent": "debugger", "quality": "agent:ok", "merged": True},
            {"action": "closed", "agent": "backend", "quality": "agent:rejected", "merged": False}
        ]
        report = quality_tracker.build_report(events, "owner/repo")
        
        self.assertIn("# Agent Quality Scores", report)
        self.assertIn("`debugger`", report)
        self.assertIn("`backend`", report)
        # Excellent (5) + Ok (4) = 9 / 2 = 4.5
        self.assertIn("**4.5**", report)
        # Rejected (0)
        self.assertIn("**0.0**", report)

if __name__ == "__main__":
    unittest.main()
