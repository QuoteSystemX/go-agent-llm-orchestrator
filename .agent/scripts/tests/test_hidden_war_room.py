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
    @patch('orchestration.hidden_war_room.bus_manager', new=None)
    def test_run_war_room_output(self):
        """Verify the 4-role debate produces expected output structure."""
        intent = "build a new storage engine"
        with patch('builtins.print') as mock_print:
            result = war_room.run_war_room(intent)

        # Collect all print calls as one string
        output = " ".join(str(call[0][0]) for call in mock_print.call_args_list if call[0])

        # Verify the presence of all 4 participants and the consensus
        self.assertIn("Opening Hidden War Room", output)
        self.assertIn("[OPTIMIST]", output)
        self.assertIn("[SKEPTIC]", output)
        self.assertIn("[USER ADVOCATE]", output)
        self.assertIn("[ARBITRATOR]", output)
        self.assertIn("CONSENSUS", output)

        # Result must be a dict with status and confidence keys
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertIn("confidence", result)

    @patch('orchestration.hidden_war_room.load_user_profile', return_value="[EXPERIMENTAL / FAST]")
    @patch('orchestration.hidden_war_room.bus_manager', new=None)
    def test_run_war_room_with_custom_profile(self, mock_profile):
        """Verify custom profile is applied to the debate context."""
        intent = "test"
        with patch('builtins.print') as mock_print:
            result = war_room.run_war_room(intent)

        output = " ".join(str(call[0][0]) for call in mock_print.call_args_list if call[0])
        self.assertIn("[EXPERIMENTAL / FAST]", output)
        self.assertIsInstance(result, dict)

    def test_parse_verdict_valid_json(self):
        """Verify _parse_verdict extracts status/confidence from JSON block."""
        text = 'Some preamble {"status": "approved", "conditions": ["c1"], "confidence": 0.9, "summary": "ok"} end'
        v = war_room._parse_verdict(text, "test")
        self.assertEqual(v["status"], "approved")
        self.assertAlmostEqual(v["confidence"], 0.9)

    def test_parse_verdict_fallback(self):
        """Verify _parse_verdict returns a fallback dict on malformed input."""
        v = war_room._parse_verdict("no json here at all", "some topic")
        self.assertIn("status", v)
        self.assertIn("confidence", v)


if __name__ == "__main__":
    unittest.main()
