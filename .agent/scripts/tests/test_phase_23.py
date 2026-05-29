
# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import unittest
import sys
import os
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

import orchestration.hidden_war_room; import sys; sys.modules['hidden_war_room'] = sys.modules['orchestration.hidden_war_room']; import orchestration.hidden_war_room as hidden_war_room
import analysis.truth_validator; import sys; sys.modules['truth_validator'] = sys.modules['analysis.truth_validator']; import analysis.truth_validator as truth_validator
import analysis.resource_forecaster; import sys; sys.modules['resource_forecaster'] = sys.modules['analysis.resource_forecaster']; import analysis.resource_forecaster as resource_forecaster
import analysis.requirement_expander; import sys; sys.modules['requirement_expander'] = sys.modules['analysis.requirement_expander']; import analysis.requirement_expander as requirement_expander

_STUB_VERDICT = '{"status": "approved", "confidence": 0.8, "conditions": [], "summary": "ok"}'


class TestPhase23(unittest.TestCase):

    @unittest.mock.patch('orchestration.hidden_war_room.query_llm_safe',
                         return_value=(_STUB_VERDICT, "stub", {}))
    @unittest.mock.patch('orchestration.hidden_war_room.bus_manager', new=None)
    def test_user_advocate_veto(self, mock_llm, *_):
        print("\n[TEST] User Advocate Veto...")
        f = StringIO()
        with redirect_stdout(f):
            result = hidden_war_room.run_war_room("use heavy enterprise framework for hello world")
        output = f.getvalue()
        self.assertIn("[OPTIMIST]", output)
        self.assertIn("[SKEPTIC]", output)
        self.assertIn("[USER ADVOCATE]", output)
        self.assertIn("[ARBITRATOR]", output)
        self.assertIn("CONSENSUS", output)
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertIn("confidence", result)

    def test_truth_validation_conflict(self):
        print("[TEST] Truth Validation Conflict...")
        f = StringIO()
        with redirect_stdout(f):
            truth_validator.validate_truth("setup auth system", [])
        output = f.getvalue()
        self.assertIn("CONFLICT_OF_TRUTH DETECTED!", output)
        self.assertIn("[LOCAL]: Use JWT", output)

    def test_budget_guardrail_veto(self):
        print("[TEST] Budget Guardrail Veto...")
        long_intent = " ".join(["word"] * 60)
        f = StringIO()
        with redirect_stdout(f):
            res = resource_forecaster.forecast_resources(long_intent)
        output = f.getvalue()
        self.assertFalse(res)
        self.assertIn("BUDGET_EXCEEDED", output)
        self.assertIn("[USER ADVOCATE]: VETO", output)

    @unittest.mock.patch('analysis.requirement_expander._search_standards', return_value=[])
    @unittest.mock.patch('analysis.requirement_expander._query_llm_safe', return_value="")
    def test_requirement_feedback_loop(self, mock_llm, mock_search):
        print("[TEST] Requirement Feedback Loop...")
        f = StringIO()
        with redirect_stdout(f):
            requirement_expander.expand_requirements("api", feedback="security first")
        output = f.getvalue()
        self.assertIn("Re-expanding requirements based on feedback: 'security first'", output)
        self.assertIn("Starting Ranked Requirement Expansion for: 'api focus on security first'", output)

if __name__ == "__main__":
    unittest.main()
