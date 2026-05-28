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

import orchestration.arbitrator as arbitrator


class TestArbitrator(unittest.TestCase):

    @patch('orchestration.arbitrator.bus_manager', new=None)
    @patch('orchestration.arbitrator.query_llm_safe')
    def test_run_consensus_flow(self, mock_llm):
        """Verify that run_consensus calls all 3 debate rounds and produces a verdict."""
        plan_id = "test-plan-1"
        plan_text = "Simple test plan: Deploy a microservice."

        # Challenger returns a valid JSON critique
        challenger_json = json.dumps({
            "critiques": [
                {"id": "CRIT-001", "category": "security", "severity": "warning",
                 "description": "Missing auth", "suggested_action": "Add JWT"}
            ]
        })
        # Proposer returns valid JSON resolution
        proposer_json = json.dumps({
            "resolutions": [
                {"critique_id": "CRIT-001", "accepted": True, "resolution": "Will add JWT"}
            ]
        })
        # Judge returns a structured verdict
        judge_json = json.dumps({
            "status": "approved_with_conditions",
            "conditions": ["Add JWT auth"],
            "confidence": 0.85,
            "risk_areas": [],
            "summary": "Solid plan with minor auth gap."
        })

        mock_llm.side_effect = [
            (challenger_json, "stub", 0),
            (proposer_json, "stub", 0),
            (judge_json, "stub", 0),
        ]

        result = arbitrator.run_consensus(plan_id, plan_text)

        self.assertEqual(mock_llm.call_count, 3)
        self.assertIn("status", result)
        self.assertIn("plan_ref", result)
        self.assertEqual(result["plan_ref"], plan_id)

    @patch('orchestration.arbitrator.bus_manager', new=None)
    @patch('orchestration.arbitrator._load_plan', return_value="")
    def test_run_consensus_plan_not_found(self, mock_load):
        """When plan text is empty, run_consensus should still execute (not crash)."""
        plan_id = "missing"

        with patch('orchestration.arbitrator.query_llm_safe') as mock_llm:
            mock_llm.return_value = ('{"critiques": []}', "stub", 0)
            # Should not raise even if plan is empty
            try:
                arbitrator.run_consensus(plan_id)
            except SystemExit:
                self.fail("run_consensus raised SystemExit unexpectedly")

    def test_parse_verdict_valid_json(self):
        """Verify _parse_verdict extracts structured data from a JSON block in text."""
        text = 'Preamble {"status": "approved", "conditions": [], "confidence": 0.9, "risk_areas": [], "summary": "all good"} end'
        v = arbitrator._parse_verdict(text, "test-plan")
        self.assertEqual(v["status"], "approved")
        self.assertAlmostEqual(v["confidence"], 0.9, places=2)
        self.assertEqual(v["plan_ref"], "test-plan")

    def test_parse_verdict_fallback(self):
        """Verify _parse_verdict returns a fallback dict on malformed input."""
        v = arbitrator._parse_verdict("no json here", "fallback-plan")
        self.assertIn("status", v)
        self.assertIn("confidence", v)
        self.assertIn("plan_ref", v)

    def test_verdict_pushed_to_bus(self):
        """Verify _push_verdict calls bus_manager.push with correct event type."""
        mock_bm = MagicMock()
        with patch('orchestration.arbitrator.bus_manager', mock_bm):
            arbitrator._push_verdict(
                plan_id="verdict-test",
                verdict={"status": "approved", "confidence": 0.9},
                plan_text="Test plan"
            )
        mock_bm.push.assert_called_once()
        args = mock_bm.push.call_args[0]
        self.assertEqual(args[0], "verdict_verdict-test")
        self.assertEqual(args[1], "verification_result")
        self.assertEqual(args[2], "arbitrator")


if __name__ == "__main__":
    unittest.main()
