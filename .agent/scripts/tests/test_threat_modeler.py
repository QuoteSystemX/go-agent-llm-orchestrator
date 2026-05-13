#!/usr/bin/env python3
import unittest
import sys
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import os
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.threat_modeler as tm

class TestThreatModeler(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_model_threats_found(self, mock_stdout):
        tm.model_threats("Implement user login system")
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Potential Security Risks Detected", output)
        self.assertIn("Brute-force attack", output)
        self.assertIn("Session hijacking", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_model_threats_none(self, mock_stdout):
        tm.model_threats("Refactor button styles")
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No immediate security threats identified", output)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_model_threats_multi(self, mock_stdout):
        tm.model_threats("Upload to database")
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("RCE via malicious file", output)
        self.assertIn("SQL Injection", output)

if __name__ == "__main__":
    unittest.main()
