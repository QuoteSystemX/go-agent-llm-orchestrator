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

import models.router_trainer as trainer

class TestRouterTrainer(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_router_trainer").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.config_dir = self.test_root / ".agent" / "config"
        self.config_dir.mkdir(parents=True)
        
        self.rules_dir = self.test_root / ".agent" / "rules"
        self.rules_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_rules_file = patch('models.router_trainer.RULES_FILE', self.config_dir / "router_rules.json")
        self.patch_lessons_file = patch('models.router_trainer.LESSONS_FILE', self.rules_dir / "LESSONS_LEARNED.md")
        
        self.patch_rules_file.start()
        self.patch_lessons_file.start()

    def tearDown(self):
        self.patch_rules_file.stop()
        self.patch_lessons_file.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_extract_lessons(self):
        content = "Intro\n### Lesson 1\nbody1\n### Lesson 2\nbody2"
        lessons = trainer.extract_lessons(content)
        self.assertEqual(len(lessons), 3) # Intro + 2 lessons
        self.assertEqual(lessons[1].strip(), "Lesson 1\nbody1")

    def test_train_missing_files(self):
        result = trainer.train()
        self.assertIn("Error", result)
        self.assertIn("router_rules.json not found", result)

    def test_train_adjustments(self):
        rules_file = self.config_dir / "router_rules.json"
        lessons_file = self.rules_dir / "LESSONS_LEARNED.md"
        
        rules = {
            "scoring": {
                "weights": {
                    "refactor": 5,
                    "unknown": 2
                }
            }
        }
        rules_file.write_text(json.dumps(rules))
        
        # Add 1 failure lesson for refactor, 2 for 'drift'
        lessons_file.write_text("""### Refactor Bug
The refactor failed because of a bug.
### Drift Error 1
Drift was found and caused an error.
### Drift Error 2
Another drift error occurred.
""")
        
        result = trainer.train()
        self.assertIn("Boosted 'refactor': 5 -> 6", result)
        self.assertIn("Added new keyword 'drift'", result)
        
        # Verify JSON updated
        new_rules = json.loads(rules_file.read_text())
        new_weights = new_rules["scoring"]["weights"]
        self.assertEqual(new_weights["refactor"], 6)
        self.assertEqual(new_weights["drift"], 5)
        self.assertEqual(new_weights["unknown"], 2)

    def test_train_no_adjustments(self):
        rules_file = self.config_dir / "router_rules.json"
        lessons_file = self.rules_dir / "LESSONS_LEARNED.md"
        
        rules = {
            "scoring": {
                "weights": {
                    "refactor": 5
                }
            }
        }
        rules_file.write_text(json.dumps(rules))
        lessons_file.write_text("### Normal Lesson\nJust a normal lesson about refactor.")
        
        result = trainer.train()
        self.assertIn("No adjustments needed", result)

if __name__ == "__main__":
    unittest.main()
