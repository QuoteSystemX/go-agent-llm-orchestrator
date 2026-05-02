import unittest
import sys
import os
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

import hidden_war_room
import truth_validator
import resource_forecaster
import requirement_expander

class TestPhase23(unittest.TestCase):

    def test_user_advocate_veto(self):
        print("\n[TEST] User Advocate Veto...")
        f = StringIO()
        with redirect_stdout(f):
            hidden_war_room.run_war_room("use heavy enterprise framework for hello world")
        output = f.getvalue()
        self.assertIn("[USER ADVOCATE]: Hold on", output)
        self.assertIn("VETO", output)
        self.assertIn("CONSENSUS REACHED: Implementation approved (Minimalist Style Enforcement)", output)

    def test_truth_validation_conflict(self):
        print("[TEST] Truth Validation Conflict...")
        f = StringIO()
        with redirect_stdout(f):
            truth_validator.validate_truth("setup auth system", [])
        output = f.getvalue()
        self.assertIn("🚨 CONFLICT_OF_TRUTH DETECTED!", output)
        self.assertIn("[LOCAL]: Use JWT", output)

    def test_budget_guardrail_veto(self):
        print("[TEST] Budget Guardrail Veto...")
        # Create a prompt long enough to exceed 50 words (50 * 1500 = 75,000 tokens > 50,000 max)
        long_intent = " ".join(["word"] * 60)
        f = StringIO()
        with redirect_stdout(f):
            res = resource_forecaster.forecast_resources(long_intent)
        output = f.getvalue()
        self.assertFalse(res)
        self.assertIn("🚨 BUDGET_EXCEEDED", output)
        self.assertIn("[USER ADVOCATE]: VETO", output)

    def test_requirement_feedback_loop(self):
        print("[TEST] Requirement Feedback Loop...")
        f = StringIO()
        with redirect_stdout(f):
            requirement_expander.expand_requirements("api", feedback="security first")
        output = f.getvalue()
        self.assertIn("🔄 Re-expanding requirements based on feedback: 'security first'", output)
        self.assertIn("Starting Ranked Requirement Expansion for: 'api focus on security first'", output)

if __name__ == "__main__":
    unittest.main()
