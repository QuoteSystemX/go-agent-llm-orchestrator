#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
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

import models.model_benchmark as benchmark

class TestModelBenchmark(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_model_benchmark").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.config_dir = self.test_root / ".agent" / "config"
        self.config_dir.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_root = patch('models.model_benchmark.REPO_ROOT', self.test_root)
        self.patch_root.start()

    def tearDown(self):
        self.patch_root.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('urllib.request.urlopen')
    def test_query_ollama_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"response": "hello world" * 10}).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        response, elapsed, tps = benchmark.query_ollama("prompt", "model")
        self.assertIn("hello world", response)
        self.assertGreaterEqual(elapsed, 0)
        self.assertGreater(tps, 0)

    @patch('urllib.request.urlopen')
    def test_query_ollama_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection Refused")
        
        response, elapsed, tps = benchmark.query_ollama("prompt", "model")
        self.assertTrue(response.startswith("ERROR"))
        self.assertEqual(tps, 0)

    def test_score_quality(self):
        self.assertEqual(benchmark.score_quality("ERROR: something", "task"), 0)
        
        # Default is 3
        self.assertEqual(benchmark.score_quality("simple response", "task"), 3)
        
        # Actionable items (+1)
        self.assertEqual(benchmark.score_quality("I recommend you fix the issue", "task"), 4)
        
        # Structured output (+1)
        self.assertEqual(benchmark.score_quality("- point 1\n- point 2", "task"), 4)
        
        # Both (+2) -> 5
        self.assertEqual(benchmark.score_quality("1. I recommend to fix it", "task"), 5)
        
        # Long response (+1), but max is 5
        long_response = "1. recommend fix\n" + "long " * 300
        self.assertEqual(benchmark.score_quality(long_response, "task"), 5)

    @patch('models.model_benchmark.query_ollama')
    def test_run_full_benchmark(self, mock_query):
        mock_query.return_value = ("1. recommend fix", 1.0, 10.0)
        
        # Write config
        rules = {
            "models": {
                "ollama": {
                    "L1": "model1",
                    "L2": "model2"
                }
            }
        }
        (self.config_dir / "router_rules.json").write_text(json.dumps(rules))
        
        with patch('sys.stdout', new=MagicMock()):
            # We run with quick=True to speed up
            results = benchmark.run_full_benchmark(quick=True)
            
        self.assertEqual(len(results), 2) # L1 and L2 for "medium" task only
        self.assertEqual(results[0].model, "model1")
        self.assertEqual(results[1].model, "model2")
        self.assertEqual(results[0].task, "medium")
        
        # Check output file
        output_path = self.bus_dir / "benchmark_results.json"
        self.assertTrue(output_path.exists())

if __name__ == "__main__":
    unittest.main()
