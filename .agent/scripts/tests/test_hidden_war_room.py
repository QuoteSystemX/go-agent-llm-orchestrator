#!/usr/bin/env python3
import unittest
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

import orchestration.hidden_war_room as war_room

class TestHiddenWarRoom(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_war_room_output(self, mock_stdout):
        intent = "build a new storage engine"
        war_room.run_war_room(intent)
        
        # Collect all print outputs
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        
        # Verify the presence of all 4 participants and the consensus
        self.assertIn("Opening Hidden War Room", output)
        self.assertIn("[OPTIMIST]:", output)
        self.assertIn("[SKEPTIC]:", output)
        self.assertIn("[USER ADVOCATE]:", output)
        self.assertIn("[ARBITRATOR]:", output)
        self.assertIn("CONSENSUS REACHED:", output)
        self.assertIn("Minimalist Style Enforcement", output)

    @patch('orchestration.hidden_war_room.get_user_profile', return_value="[EXPERIMENTAL / FAST]")
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_war_room_with_custom_profile(self, mock_stdout, mock_profile):
        intent = "test"
        war_room.run_war_room(intent)
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("USER DNA DETECTED: [EXPERIMENTAL / FAST]", output)

if __name__ == "__main__":
    unittest.main()
