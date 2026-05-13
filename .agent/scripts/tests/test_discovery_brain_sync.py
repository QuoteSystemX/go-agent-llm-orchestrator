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

import knowledge.discovery_brain_sync as sync

class TestDiscoveryBrainSync(unittest.TestCase):
    @patch('knowledge.discovery_brain_sync.brain.search_lessons')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_sync_with_global_brain_success(self, mock_stdout, mock_search):
        mock_search.return_value = [
            {"project": "ProjectA", "summary": "Found X"},
            {"project": "ProjectB", "summary": "Found Y"}
        ]
        
        sync.sync_with_global_brain("Test intent")
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("ProjectA", output)
        self.assertIn("Found X", output)
        self.assertIn("ProjectB", output)
        self.assertIn("Found Y", output)

    @patch('knowledge.discovery_brain_sync.brain.search_lessons')
    @patch('sys.stdout', new_callable=MagicMock)
    def test_sync_with_global_brain_empty(self, mock_stdout, mock_search):
        mock_search.return_value = []
        
        sync.sync_with_global_brain("Unique intent")
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("No specific matches found", output)

if __name__ == "__main__":
    unittest.main()
