#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import analysis.ux_conversion_audit as uxa

class TestUXAuditor(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_ux_audit").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        (self.test_root / ".agent" / "bus").mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_check_fitts_law(self):
        auditor = uxa.UXAuditor(".")
        
        # Large button
        btn_large = {"class": ["btn-lg"]}
        passed, msg = auditor.check_fitts_law(btn_large)
        self.assertTrue(passed)
        
        # Small button
        btn_small = {"class": ["btn-sm"]}
        passed, msg = auditor.check_fitts_law(btn_small)
        self.assertFalse(passed)
        self.assertIn("Fitts' Law", msg)

    def test_heading_skip(self):
        html = "<h1>Title</h1><h3>Subtitle</h3>"
        f = self.test_root / "test.html"
        f.write_text(html)
        
        auditor = uxa.UXAuditor(self.test_root)
        result = auditor.audit_file(f)
        
        self.assertFalse(result["passed"])
        self.assertTrue(any("Heading level skip" in i["issue"] for i in result["a11y_issues"]))

    def test_missing_aria_label(self):
        html = "<button class='icon-only'></button>" # No text, no aria-label
        f = self.test_root / "btn.html"
        f.write_text(html)
        
        auditor = uxa.UXAuditor(self.test_root)
        result = auditor.audit_file(f)
        
        self.assertTrue(any("Missing aria-label" in i["issue"] for i in result["a11y_issues"]))

    def test_full_run(self):
        (self.test_root / "ui").mkdir()
        (self.test_root / "ui" / "dashboard.html").write_text("<h1>Dashboard</h1>")
        
        auditor = uxa.UXAuditor(self.test_root)
        auditor.run()
        
        self.assertEqual(len(auditor.results), 1)
        self.assertEqual(auditor.results[0]["file"], "ui/dashboard.html")

if __name__ == "__main__":
    unittest.main()
