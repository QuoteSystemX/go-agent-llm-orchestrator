#!/usr/bin/env python3
import unittest
import json
import os
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

import models.model_router as model_router

class TestModelRouter(unittest.TestCase):
    def test_calculate_score_keywords(self):
        rules = {
            "scoring": {
                "weights": {
                    "refactor": 3,
                    "fix": 1
                }
            }
        }
        # Base score is 5
        score = model_router.calculate_score("refactor code", rules)
        self.assertEqual(score, 8)
        
        score = model_router.calculate_score("fix bug", rules)
        self.assertEqual(score, 6)

    @patch('models.model_router.get_failure_score', return_value=2)
    @patch('models.model_router.get_budget_penalty', return_value=-1)
    def test_calculate_score_complex(self, mock_budget, mock_fail):
        rules = {"scoring": {"weights": {"critical": 5}}}
        # 5 (base) + 5 (keyword) + 2 (fail) - 1 (budget) = 11
        score = model_router.calculate_score("critical task", rules)
        self.assertEqual(score, 11)

    def test_resolve_provider_env_override(self):
        with patch.dict(os.environ, {"AGENT_PROVIDER": "custom"}):
            provider, alive, url = model_router.resolve_provider({})
            self.assertEqual(provider, "custom")

    @patch('models.model_router.check_ollama_health')
    def test_resolve_provider_hybrid(self, mock_health):
        mock_health.return_value = True
        rules = {
            "hybrid_routing": {
                "enabled": True,
                "primary_provider": "ollama",
                "ollama_base_url": "http://localhost:11434"
            }
        }
        provider, alive, url = model_router.resolve_provider(rules)
        self.assertEqual(provider, "ollama")
        self.assertTrue(alive)

    def test_pick_best_available_local(self):
        model_map = {"L2": "primary:1", "L2_alt": ["alt:1", "alt:2"]}
        model_rankings = {
            "primary:1": {"rank_score": 50},
            "alt:1": {"rank_score": 60} # Alt is better
        }
        
        with patch('models.model_router.get_ollama_local_models', return_value={"primary:1", "alt:1"}):
            model_id, reason = model_router.pick_best_available(
                "L2", model_map, model_rankings, True, "http://url"
            )
            # Should pick alt:1 because it has higher rank_score
            self.assertEqual(model_id, "alt:1")
            self.assertIn("rank-score 60.0", reason)

    @patch('models.model_router.load_json_safe')
    @patch('models.model_router.resolve_provider')
    def test_route_end_to_end(self, mock_resolve, mock_load):
        mock_load.return_value = {
            "scoring": {"thresholds": {"L1": 3, "L2": 7, "L3": 10, "L4": 13}, "weights": {}},
            "models": {"ollama": {"L2": "local:1"}},
            "model_rankings": {"local:1": {"rank_score": 10}}
        }
        mock_resolve.return_value = ("ollama", True, "http://localhost")
        
        with patch('models.model_router.get_ollama_local_models', return_value={"local:1"}):
            result = model_router.route("simple task")
            self.assertEqual(result.model_id, "local:1")
            self.assertEqual(result.tier, "L2")
            self.assertEqual(result.provider, "ollama")

if __name__ == "__main__":
    unittest.main()
