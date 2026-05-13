#!/usr/bin/env python3
import unittest
import json
import sys
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.policy_guardrail as policy_guardrail

class TestPolicyGuardrail(unittest.TestCase):
    def test_check_purple_ban(self):
        # Should fail for CSS with purple
        issues = policy_guardrail.check_purple_ban("color: purple;", ".css")
        self.assertTrue(any("Forbidden color" in i for i in issues))
        
        # Should NOT fail for non-visual files
        issues = policy_guardrail.check_purple_ban("purple", ".py")
        self.assertEqual(len(issues), 0)
        
        # Should catch hex codes
        issues = policy_guardrail.check_purple_ban("background: #800080;", ".tsx")
        self.assertTrue(len(issues) > 0)

    def test_check_secrets(self):
        # Should catch API key assignments
        issues = policy_guardrail.check_secrets('api_key = "123456"')
        self.assertTrue(any("secret/key leak" in i for i in issues))
        
        # Should catch tokens
        issues = policy_guardrail.check_secrets('TOKEN = "abcde"')
        self.assertTrue(len(issues) > 0)
        
        # Should NOT catch innocent mentions
        issues = policy_guardrail.check_secrets('this is a secret message')
        self.assertEqual(len(issues), 0)

    def test_check_prose_first(self):
        # Should fail for wiki file missing Intuition
        wiki_file = "wiki/something.md"
        issues = policy_guardrail.check_prose_first("No intro here", wiki_file)
        self.assertTrue(any("Missing 'Intuition'" in i for i in issues))
        
        # Should pass if Intuition is present
        issues = policy_guardrail.check_prose_first("Intuition: This is why...", wiki_file)
        self.assertEqual(len(issues), 0)
        
        # Should ignore non-wiki files
        issues = policy_guardrail.check_prose_first("No intro", "src/main.py")
        self.assertEqual(len(issues), 0)

if __name__ == "__main__":
    unittest.main()
