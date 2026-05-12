#!/usr/bin/env python3
import unittest
import json
import shutil
from pathlib import Path
import sys

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import lib.paths
import models.prompt_optimizer; import sys; sys.modules['prompt_optimizer'] = sys.modules['models.prompt_optimizer']; import models.prompt_optimizer as prompt_optimizer

class TestPromptOptimizer(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_optimizer"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override paths
        self.original_bus = lib.paths.BUS_DIR
        lib.paths.BUS_DIR = self.test_root / ".agent" / "bus"
        prompt_optimizer.BUS_DIR = lib.paths.BUS_DIR
        
        # Mock bus context
        lib.paths.BUS_DIR.mkdir(parents=True, exist_ok=True)
        context = {
            "objects": [
                {
                    "type": "telemetry",
                    "author": "agent_a",
                    "content": {"total_tokens": 10000}
                },
                {
                    "type": "telemetry",
                    "author": "agent_a",
                    "content": {"total_tokens": 60000}
                },
                {
                    "type": "telemetry",
                    "author": "agent_b",
                    "content": {"total_tokens": 1000}
                }
            ]
        }
        with open(lib.paths.BUS_DIR / "context.json", "w") as f:
            json.dump(context, f)

    def tearDown(self):
        lib.paths.BUS_DIR = self.original_bus
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_analyze(self):
        report = prompt_optimizer.analyze_telemetry()
        
        self.assertIn("🤖 Agent: agent_a", report)
        # (10000 + 60000) / 2 = 35000 -> TIP
        self.assertIn("💡 TIP", report)
        self.assertIn("Average per call: 35000.0", report)
        
        self.assertIn("🤖 Agent: agent_b", report)
        # 1000 -> EFFICIENT
        self.assertIn("✅ EFFICIENT", report)

if __name__ == "__main__":
    unittest.main()
