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
import orchestration.personality_adapter; import sys; sys.modules['personality_adapter'] = sys.modules['orchestration.personality_adapter']; import orchestration.personality_adapter as personality_adapter

class TestPersonalityAdapter(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_persona"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Override paths
        self.original_rules = lib.paths.RULES_DIR
        self.original_root = lib.paths.REPO_ROOT
        
        lib.paths.REPO_ROOT = self.test_root
        lib.paths.RULES_DIR = self.test_root / ".agent" / "rules"
        personality_adapter.REPO_ROOT = self.test_root
        personality_adapter.PERSONA_FILE = lib.paths.RULES_DIR / "PERSONA.md"
        
        # Mock PERSONA.md
        lib.paths.RULES_DIR.mkdir(parents=True)
        persona_content = """# Persona
## 🧬 Core DNA: [PRAGMATIC / MINIMALIST]

## Stylistic Preferences
- No verbose intro
- Direct code examples
- Markdown tables for data
"""
        personality_adapter.PERSONA_FILE.write_text(persona_content)

    def tearDown(self):
        lib.paths.RULES_DIR = self.original_rules
        lib.paths.REPO_ROOT = self.original_root
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_adapt(self):
        personality_adapter.adapt_personality()
        
        bus_file = self.test_root / ".agent" / "bus" / "personality_profile.json"
        self.assertTrue(bus_file.exists())
        
        with open(bus_file) as f:
            data = json.load(f)
            self.assertEqual(data["dna"], "PRAGMATIC / MINIMALIST")
            self.assertIn("No verbose intro", data["preferences"])

if __name__ == "__main__":
    unittest.main()
