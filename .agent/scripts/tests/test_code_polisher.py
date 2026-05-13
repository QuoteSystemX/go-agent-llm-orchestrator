#!/usr/bin/env python3
import unittest
import sys
import os
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

import dev.code_polisher as polisher

class TestCodePolisher(unittest.TestCase):
    @patch('subprocess.check_output')
    def test_run_polish_with_changes(self, mock_output):
        mock_output.return_value = b"file1.py\nfile2.py"
        
        with patch('sys.stdout', new=MagicMock()):
            polisher.run_polish()
            
        mock_output.assert_called_once()

    @patch('subprocess.check_output')
    def test_run_polish_no_git(self, mock_output):
        mock_output.side_effect = Exception("Git not found")
        
        with patch('sys.stdout', new=MagicMock()):
            polisher.run_polish()
            
        # It should fallback to globbing and not crash
        mock_output.assert_called_once()

if __name__ == "__main__":
    unittest.main()
