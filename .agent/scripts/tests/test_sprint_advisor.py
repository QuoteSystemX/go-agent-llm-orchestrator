#!/usr/bin/env python3
import unittest
import json
import sys
import shutil
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.sprint_advisor as sprint_advisor

class TestSprintAdvisor(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_sprint_root"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.foresight_dir = self.test_root / ".agent" / "foresight"
        self.foresight_dir.mkdir(parents=True)
        self.foresight_file = self.foresight_dir / "latest_risk_report.json"

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def setup_mock_path(self, mock_path):
        # We need to mock Path(__file__).resolve().parents[3] to be self.test_root
        # In the script: repo_root = Path(__file__).resolve().parents[3]
        # Then: foresight_file = repo_root / ".agent" / "foresight" / "latest_risk_report.json"
        
        mock_instance = MagicMock()
        # The first call to Path() in the script is Path(__file__)
        mock_path.return_value = mock_instance
        
        # mock_instance.resolve().parents[3] -> self.test_root
        mock_instance.resolve.return_value.parents = [None, None, None, self.test_root]

    @patch('orchestration.sprint_advisor.Path')
    def test_generate_advice_missing_file(self, mock_path):
        self.setup_mock_path(mock_path)
            
        with patch('sys.stdout', new=StringIO()) as fake_out:
            sprint_advisor.generate_sprint_advice()
            self.assertIn("No foresight report found", fake_out.getvalue())

    @patch('orchestration.sprint_advisor.Path')
    def test_generate_advice_no_risks(self, mock_path):
        self.setup_mock_path(mock_path)
        self.foresight_file.write_text(json.dumps([
            {"file": "ok.py", "risk_score": 10}
        ]))
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            sprint_advisor.generate_sprint_advice()
            self.assertIn("All systems stable", fake_out.getvalue())

    @patch('orchestration.sprint_advisor.Path')
    def test_generate_advice_critical_risks(self, mock_path):
        self.setup_mock_path(mock_path)
        self.foresight_file.write_text(json.dumps([
            {"file": "messy.py", "risk_score": 80, "complexity": 100, "churn": 5, "trend": 10}
        ]))
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            sprint_advisor.generate_sprint_advice()
            output = fake_out.getvalue()
            self.assertIn("DETECTED 1 DEGRADATION RISKS", output)
            self.assertIn("Refactor messy.py", output)
            self.assertIn("Trend: Increasing (+10)", output)

if __name__ == "__main__":
    unittest.main()
