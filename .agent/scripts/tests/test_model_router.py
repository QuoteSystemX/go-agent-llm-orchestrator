#!/usr/bin/env python3
"""Tests for model_router.py — routing logic and env-var resolution."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))
from model_router import route, resolve_env_var


class TestResolveEnvVar(unittest.TestCase):
    def test_plain_string_passthrough(self):
        self.assertEqual(resolve_env_var("claude-opus-4-20250514"), "claude-opus-4-20250514")

    def test_env_var_with_default(self):
        # Without env var set, should return default
        result = resolve_env_var("${MODEL_TEST_XYZ:-fallback-model}")
        self.assertEqual(result, "fallback-model")

    def test_env_var_set(self):
        os.environ["MODEL_TEST_SET"] = "my-custom-model"
        try:
            result = resolve_env_var("${MODEL_TEST_SET:-default}")
            self.assertEqual(result, "my-custom-model")
        finally:
            del os.environ["MODEL_TEST_SET"]


class TestRouteLogic(unittest.TestCase):
    @patch("model_router.RULES_FILE", Path("/nonexistent/path"))
    def test_no_rules_uses_default(self):
        with patch("sys.stdout", new_callable=StringIO):
            result = route("some task")
        self.assertEqual(result, "claude-sonnet-4-20250514")

    @patch("model_router.RULES_FILE", Path("/nonexistent/path"))
    def test_manual_override(self):
        with patch("sys.stdout", new_callable=StringIO):
            result = route("some task", override_model="my-model")
        self.assertEqual(result, "my-model")


if __name__ == "__main__":
    unittest.main()
