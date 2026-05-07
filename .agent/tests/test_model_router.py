#!/usr/bin/env python3
"""Tests for model_router.py — covers all tiers, hybrid routing, quality ranking,
Ollama health scenarios, warning output, and error handling."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

import model_router
from model_router import (
    RoutingResult,
    calculate_score,
    check_ollama_health,
    get_ollama_local_models,
    pick_best_available,
    route,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

RULES = {
    "scoring": {
        "thresholds": {"L1": 3, "L2": 7, "L3": 10, "L4": 13},
        "weights": {
            "security": 7, "architecture": 6, "audit": 6,
            "refactor": 4, "implement": 2, "fix": 2, "add": 2,
            "lint": -2, "typo": -5, "readme": -5, "documentation": -3,
        },
    },
    "models": {
        "ollama": {
            "L1": "qwen3:4b",       "L1_alt": ["qwen3:1.7b", "gemma3:4b"],
            "L2": "qwen3:14b",      "L2_alt": ["deepseek-coder-v2:16b"],
            "L3": "devstral:24b",   "L3_alt": ["deepseek-r1:32b"],
            "L4": "qwen3-coder:30b-a3b", "L4_alt": ["qwen2.5-coder:32b"],
        },
        "antigravity": {
            "L1": "gemini-3-flash",
            "L2": "gemini-3.1-pro-low",
            "L3": "gemini-3.1-pro-high",
            "L4": "gpt-oss-120b",
        },
    },
    "model_quality_scores": {
        "qwen3:4b": 52, "qwen3:1.7b": 40, "gemma3:4b": 48,
        "qwen3:14b": 71, "deepseek-coder-v2:16b": 68,
        "devstral:24b": 82, "deepseek-r1:32b": 85,
        "qwen3-coder:30b-a3b": 88, "qwen2.5-coder:32b": 84,
        "gemini-3-flash": 60, "gemini-3.1-pro-low": 75,
        "gemini-3.1-pro-high": 88, "gpt-oss-120b": 95,
    },
    "hybrid_routing": {
        "enabled": True,
        "primary_provider": "ollama",
        "cloud_fallback_provider": "antigravity",
        "ollama_base_url": "http://localhost:11434",
        "ollama_health_timeout_ms": 1500,
        "cloud_on_tiers": ["L4"],
    },
    "domain_affinity": {},
    "fallbacks": {"L1": "L2", "L2": "L3", "L3": "L4", "L4": "L4"},
}


# ---------------------------------------------------------------------------
# 1. Score calculation — tier boundaries
# ---------------------------------------------------------------------------

class TestCalculateScore(unittest.TestCase):
    def _score(self, desc):
        return calculate_score(desc, RULES)

    def test_l1_simple_lint(self):
        s = self._score("fix lint issues")
        # "fix" +2, "lint" -2 => net 0 + base 5 = 5... but "lint" weight -2 → 5
        # Actually: base=5, fix=+2, lint=-2 → 5. Within L2 threshold (≤7).
        # Just assert it stays low
        self.assertLessEqual(s, 7)

    def test_l1_typo(self):
        s = self._score("fix a typo in readme")
        # base=5, fix=+2, typo=-5, readme=-5 → max(1, 5+2-5-5)= max(1,-3)=1
        self.assertEqual(s, 1)

    def test_l2_implement(self):
        s = self._score("implement a new feature")
        # base=5, implement=+2 → 7  (exactly at L2 threshold)
        self.assertGreater(s, 3)
        self.assertLessEqual(s, 7)

    def test_l3_security(self):
        s = self._score("security audit of the API")
        # base=5, security=+7, audit=+6 → 18 (capped)
        self.assertGreater(s, 10)

    def test_l4_architecture_refactor(self):
        s = self._score("architecture refactor for the whole system")
        # base=5, architecture=+6, refactor=+4 → 15 → L4
        self.assertGreater(s, 13)

    def test_score_clamped_min(self):
        s = self._score("typo readme documentation")
        self.assertGreaterEqual(s, 1)

    def test_score_clamped_max(self):
        s = self._score("security architecture audit refactor implement")
        self.assertLessEqual(s, 18)


# ---------------------------------------------------------------------------
# 2. Ollama health check
# ---------------------------------------------------------------------------

class TestCheckOllamaHealth(unittest.TestCase):
    def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("model_router.urllib.request.urlopen", return_value=mock_resp):
            self.assertTrue(check_ollama_health("http://localhost:11434"))

    def test_returns_false_on_connection_error(self):
        import urllib.error
        with patch("model_router.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("refused")):
            self.assertFalse(check_ollama_health("http://localhost:11434"))

    def test_returns_false_on_timeout(self):
        with patch("model_router.urllib.request.urlopen", side_effect=OSError("timeout")):
            self.assertFalse(check_ollama_health("http://localhost:11434", timeout_ms=100))

    def test_returns_false_on_unexpected_error(self):
        with patch("model_router.urllib.request.urlopen", side_effect=Exception("boom")):
            self.assertFalse(check_ollama_health("http://localhost:11434"))


# ---------------------------------------------------------------------------
# 3. get_ollama_local_models
# ---------------------------------------------------------------------------

class TestGetOllamaLocalModels(unittest.TestCase):
    def _mock_tags(self, names):
        payload = json.dumps({"models": [{"name": n} for n in names]}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = payload
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_returns_model_set(self):
        with patch("model_router.urllib.request.urlopen",
                   return_value=self._mock_tags(["qwen3:4b", "devstral:24b"])):
            models = get_ollama_local_models("http://localhost:11434")
        self.assertEqual(models, {"qwen3:4b", "devstral:24b"})

    def test_returns_empty_on_error(self):
        import urllib.error
        with patch("model_router.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("no connection")):
            models = get_ollama_local_models("http://localhost:11434")
        self.assertEqual(models, set())

    def test_returns_empty_list(self):
        with patch("model_router.urllib.request.urlopen",
                   return_value=self._mock_tags([])):
            models = get_ollama_local_models("http://localhost:11434")
        self.assertEqual(models, set())


# ---------------------------------------------------------------------------
# 4. pick_best_available — quality ranking logic
# ---------------------------------------------------------------------------

class TestPickBestAvailable(unittest.TestCase):
    MODEL_MAP = RULES["models"]["ollama"]
    QUALITY = RULES["model_quality_scores"]
    URL = "http://localhost:11434"

    def _pick(self, tier, available_models=None, ollama_alive=True):
        """Helper: mock /api/tags and call pick_best_available."""
        if available_models is None:
            available_models = set()

        def fake_get_local(_url):
            return available_models

        with patch("model_router.get_ollama_local_models", side_effect=fake_get_local):
            return pick_best_available(
                tier=tier,
                model_map=self.MODEL_MAP,
                quality_scores=self.QUALITY,
                ollama_alive=ollama_alive,
                ollama_base_url=self.URL,
            )

    # --- Ollama alive, primary model available ---
    def test_l1_primary_available(self):
        model, reason = self._pick("L1", {"qwen3:4b"})
        self.assertEqual(model, "qwen3:4b")
        self.assertIn("locally available", reason)

    def test_l2_primary_available(self):
        model, reason = self._pick("L2", {"qwen3:14b"})
        self.assertEqual(model, "qwen3:14b")

    def test_l3_primary_available(self):
        model, reason = self._pick("L3", {"devstral:24b"})
        self.assertEqual(model, "devstral:24b")

    # --- Ollama alive, only alt available — picks highest quality ---
    def test_l2_alt_higher_quality_than_primary(self):
        # deepseek-coder-v2:16b score=68 < qwen3:14b score=71
        # → if primary not available, alt should be used
        model, reason = self._pick("L2", {"deepseek-coder-v2:16b"})
        self.assertEqual(model, "deepseek-coder-v2:16b")
        self.assertIn("alt over", reason)

    def test_l3_alt_has_higher_score(self):
        # deepseek-r1:32b (85) > devstral:24b (82)
        # Both available: router should pick deepseek-r1 (higher quality)
        model, reason = self._pick("L3", {"devstral:24b", "deepseek-r1:32b"})
        self.assertEqual(model, "deepseek-r1:32b")

    # --- Ollama alive, NO models available → returns None ---
    def test_no_models_returns_none(self):
        model, reason = self._pick("L2", available_models=set())
        self.assertIsNone(model)
        self.assertIn("cloud fallback", reason)

    def test_no_models_at_all_returns_none(self):
        # Simulate empty /api/tags (brand-new Ollama)
        model, reason = self._pick("L1", available_models=set())
        self.assertIsNone(model)

    # --- Ollama NOT alive → cloud quality ranking (no availability check) ---
    def test_cloud_mode_picks_highest_quality(self):
        cloud_map = RULES["models"]["antigravity"]
        model, reason = pick_best_available(
            tier="L2",
            model_map=cloud_map,
            quality_scores=self.QUALITY,
            ollama_alive=False,
            ollama_base_url=self.URL,
        )
        self.assertEqual(model, "gemini-3.1-pro-low")
        self.assertIn("quality-ranked", reason)


# ---------------------------------------------------------------------------
# 5. Full route() integration — all tiers
# ---------------------------------------------------------------------------

def _make_route_mocks(ollama_alive: bool, local_models: set):
    """Return a context-manager stack that patches route() internals."""
    import contextlib

    @contextlib.contextmanager
    def ctx():
        with patch("model_router.load_json_safe", return_value=RULES), \
             patch("model_router.check_ollama_health", return_value=ollama_alive), \
             patch("model_router.get_ollama_local_models", return_value=local_models), \
             patch("model_router.log_routing_event"):
            yield

    return ctx()


class TestRouteAllTiers(unittest.TestCase):
    """All tiers with Ollama alive and primary models pulled."""

    def _route(self, task):
        local = {
            "qwen3:4b", "qwen3:14b", "devstral:24b",
            "qwen3-coder:30b-a3b",
        }
        with _make_route_mocks(ollama_alive=True, local_models=local):
            return route(task)

    def test_l1_typo_task(self):
        result = self._route("fix a typo in readme")
        self.assertIsInstance(result, RoutingResult)
        self.assertEqual(result.tier, "L1")
        self.assertEqual(result.model_id, "qwen3:4b")
        self.assertEqual(result.provider, "ollama")
        self.assertEqual(result.warning, "")

    def test_l2_implement_task(self):
        result = self._route("implement a new feature")
        self.assertEqual(result.tier, "L2")
        self.assertEqual(result.model_id, "qwen3:14b")
        self.assertEqual(result.provider, "ollama")

    def test_l3_debug_task(self):
        # "refactor" (+4) + base(5) = 9 → L3 (threshold > 7, ≤ 10)
        result = self._route("refactor this function")
        self.assertEqual(result.tier, "L3")
        self.assertEqual(result.model_id, "devstral:24b")
        self.assertEqual(result.provider, "ollama")

    def test_l4_always_cloud(self):
        # L4 is forced to cloud regardless of Ollama status
        result = self._route("security audit and architecture refactor")
        self.assertEqual(result.tier, "L4")
        self.assertEqual(result.provider, "antigravity")
        self.assertEqual(result.model_id, "gpt-oss-120b")
        self.assertEqual(result.warning, "")

    def test_result_has_score(self):
        result = self._route("implement a feature")
        self.assertGreater(result.score, 0)


# ---------------------------------------------------------------------------
# 6. Cloud fallback — Ollama unreachable
# ---------------------------------------------------------------------------

class TestRouteOllamaUnreachable(unittest.TestCase):
    def _route(self, task):
        with _make_route_mocks(ollama_alive=False, local_models=set()):
            return route(task)

    def test_l1_goes_to_cloud(self):
        result = self._route("fix a typo in readme")
        self.assertEqual(result.provider, "antigravity")
        self.assertEqual(result.model_id, "gemini-3-flash")
        self.assertEqual(result.warning, "")  # No warning — Ollama is simply down

    def test_l2_goes_to_cloud(self):
        result = self._route("implement a feature")
        self.assertEqual(result.provider, "antigravity")
        self.assertEqual(result.model_id, "gemini-3.1-pro-low")

    def test_l3_goes_to_cloud(self):
        # "refactor" (+4) + base(5) = 9 → L3
        result = self._route("refactor this function")
        self.assertEqual(result.tier, "L3")
        self.assertEqual(result.provider, "antigravity")
        self.assertEqual(result.model_id, "gemini-3.1-pro-high")


# ---------------------------------------------------------------------------
# 7. Warning — Ollama alive but models not pulled
# ---------------------------------------------------------------------------

class TestRouteOllamaAliveNoModels(unittest.TestCase):
    def _route(self, task):
        with _make_route_mocks(ollama_alive=True, local_models=set()):
            return route(task)

    def test_warning_present(self):
        result = self._route("implement a feature")
        self.assertNotEqual(result.warning, "")
        self.assertIn("Ollama is running", result.warning)
        self.assertIn("CLOUD", result.warning)

    def test_pull_hints_generated(self):
        result = self._route("implement a feature")
        self.assertTrue(len(result.pull_hints) > 0)
        for hint in result.pull_hints:
            self.assertTrue(hint.startswith("ollama pull "))

    def test_falls_back_to_cloud_model(self):
        result = self._route("implement a feature")
        self.assertEqual(result.provider, "antigravity")
        self.assertIn("gemini", result.model_id)

    def test_l4_no_warning_even_if_no_local_models(self):
        # L4 always goes to cloud — warning is irrelevant
        result = self._route("security audit architecture refactor")
        self.assertEqual(result.provider, "antigravity")
        self.assertEqual(result.warning, "")  # No Ollama warning for cloud-only tiers

    def test_warning_contains_pull_commands(self):
        result = self._route("implement a feature")
        self.assertIn("ollama pull qwen3:14b", result.warning)


# ---------------------------------------------------------------------------
# 8. Manual model override
# ---------------------------------------------------------------------------

class TestRouteOverride(unittest.TestCase):
    def test_override_skips_all_logic(self):
        with _make_route_mocks(ollama_alive=False, local_models=set()):
            result = route("implement a feature", override_model="my-custom-model")
        self.assertEqual(result, "my-custom-model")


# ---------------------------------------------------------------------------
# 9. RoutingResult str representation (backward compat)
# ---------------------------------------------------------------------------

class TestRoutingResult(unittest.TestCase):
    def test_str_returns_model_id(self):
        r = RoutingResult(model_id="qwen3:14b", tier="L2", provider="ollama", score=7)
        self.assertEqual(str(r), "qwen3:14b")

    def test_warning_defaults_empty(self):
        r = RoutingResult(model_id="qwen3:4b", tier="L1", provider="ollama", score=2)
        self.assertEqual(r.warning, "")
        self.assertEqual(r.pull_hints, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
