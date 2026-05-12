#!/usr/bin/env python3
import unittest
import io
from contextlib import redirect_stdout
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

import orchestration.hidden_war_room; import sys; sys.modules['hidden_war_room'] = sys.modules['orchestration.hidden_war_room']; import orchestration.hidden_war_room as hidden_war_room

class TestHiddenWarRoom(unittest.TestCase):
    def test_run_war_room(self):
        f = io.StringIO()
        with redirect_stdout(f):
            hidden_war_room.run_war_room("test intent")
        output = f.getvalue()
        
        self.assertIn("⚔️  Opening Hidden War Room", output)
        self.assertIn("👤 USER DNA DETECTED", output)
        self.assertIn("✅ CONSENSUS REACHED", output)
        self.assertIn("USER ADVOCATE", output)

if __name__ == "__main__":
    unittest.main()
