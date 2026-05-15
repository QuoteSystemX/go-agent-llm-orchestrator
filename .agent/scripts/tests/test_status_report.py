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

import health.status_report as status_report

class TestStatusReport(unittest.TestCase):
    @patch('health.status_report.REPO_ROOT', Path('/tmp/fake_repo'))
    @patch('health.status_report.BUS_DIR', Path('/tmp/fake_repo/.agent/bus'))
    @patch('health.status_report.Path.exists')
    @patch('health.status_report.Path.stat')
    @patch('health.status_report.open')
    @patch('health.status_report.subprocess.run')
    @patch('drift_detector.detect_drift')
    @patch('urllib.request.urlopen')
    def test_calculate_health_perfect(self, mock_url, mock_drift, mock_run, mock_open, mock_stat, mock_exists):
        # Setup perfect score scenario
        mock_exists.return_value = False 
        mock_drift.return_value = []
        
        # Mock parallel run results
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock Neural Memory check (Ollama)
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"models": [{"name": "mxbai-embed-large"}]}).encode()
        mock_url.return_value.__enter__.return_value = mock_response

        with patch('health.status_report.load_json_safe', return_value={}):
            score, metrics = status_report.calculate_health()
            
            self.assertTrue(score > 80)
            self.assertEqual(metrics["Drift"], "0 issues")
            self.assertEqual(metrics["Neural Memory"], "READY")

    @patch('health.status_report.REPO_ROOT', Path('/tmp/fake_repo'))
    @patch('drift_detector.detect_drift')
    @patch('urllib.request.urlopen')
    def test_calculate_health_with_drift(self, mock_url, mock_drift):
        mock_drift.return_value = ["drift 1", "drift 2"]
        
        # Mock Neural Memory failure
        mock_url.side_effect = Exception("Offline")

        with patch('health.status_report._safe_import', return_value=lambda: {}):
            with patch('health.status_report.Path.exists', return_value=False):
                with patch('health.status_report.load_json_safe', return_value={}):
                    score, metrics = status_report.calculate_health()
                    
                    self.assertEqual(metrics["Drift"], "2 issues")
                    self.assertEqual(metrics["Neural Memory"], "OFFLINE")

if __name__ == "__main__":
    unittest.main()
