#!/usr/bin/env python3
"""Tests for Contrastive Verification Loop (Option C) in output_bridge.py."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"

def _load_verifier():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        dev_module = __import__("dev.output_bridge", fromlist=["run_contrastive_validation"])
        return dev_module.run_contrastive_validation
    except ImportError:
        sys.path.insert(0, str(SCRIPTS_DIR / "dev"))
        output_bridge = __import__("output_bridge", fromlist=["run_contrastive_validation"])
        return output_bridge.run_contrastive_validation

run_contrastive_validation = _load_verifier()

class TestContrastiveVerifier(unittest.TestCase):

    def test_l1_l2_skips_validation(self):
        # L1 tier response
        content_l1 = (
            "🤖 Flow: **[L1]** | 🧠 Model: gemini-3-flash\n"
            "🎯 **Context/Goal**: Fix a typo in readme.\n"
            "🛠 **Technical Implementation**: Fixed spelling.\n"
            "📂 **Impacted Components**: file:///README.md\n"
            "📈 **Outcome/Result**: Done."
        )
        # Should return True immediately without calling LLM or git diff
        with patch("subprocess.check_output") as mock_git:
            res = run_contrastive_validation(content_l1)
            self.assertTrue(res)
            mock_git.assert_not_called()

    @patch("subprocess.check_output")
    def test_l3_no_git_changes_skips(self, mock_git):
        # L3 tier response
        content_l3 = (
            "🤖 Flow: **[L3]** | 🧠 Model: gemini-3.1-pro-high\n"
            "🎯 **Context/Goal**: Refactor authentication handler.\n"
            "🛠 **Technical Implementation**: Updated auth logic.\n"
            "📂 **Impacted Components**: file:///auth.py\n"
            "📈 **Outcome/Result**: Done."
        )
        # git diff returns empty string
        mock_git.return_value = b""
        res = run_contrastive_validation(content_l3)
        self.assertTrue(res)
        mock_git.assert_called()

    @patch("subprocess.check_output")
    @patch("lib.llm_client.query_llm_safe")
    def test_contrastive_verification_passes(self, mock_query, mock_git):
        # L3 response
        content_l3 = (
            "🤖 Flow: **[L3]** | 🧠 Model: gemini-3.1-pro-high\n"
            "🎯 **Context/Goal**: Refactor authentication handler.\n"
            "🛠 **Technical Implementation**: Updated auth logic.\n"
            "📂 **Impacted Components**: file:///auth.py\n"
            "📈 **Outcome/Result**: Done."
        )
        
        # Git diff returns some changes
        mock_git.return_value = b"diff --git a/auth.py b/auth.py\n--- a/auth.py\n+++ b/auth.py\n@@ -10,2 +10,2 @@\n-def login(): pass\n+def login_user(): pass"
        
        # LLM returns valid passed JSON
        mock_query.return_value = ('{"passed": true, "hallucinations": []}', "ollama", {})
        
        res = run_contrastive_validation(content_l3)
        self.assertTrue(res)
        mock_query.assert_called_once()

    @patch("subprocess.check_output")
    @patch("lib.llm_client.query_llm_safe")
    def test_contrastive_verification_veto(self, mock_query, mock_git):
        # L4 response
        content_l4 = (
            "🤖 Flow: **[L4]** | 🧠 Model: gpt-oss-120b\n"
            "🎯 **Context/Goal**: Implement secure token validation.\n"
            "🛠 **Technical Implementation**: Added auth call to secure_vault.get_rsa_keys().\n"
            "📂 **Impacted Components**: file:///auth.py\n"
            "📈 **Outcome/Result**: Done."
        )
        
        # Git diff shows we only updated comments, no get_rsa_keys was implemented!
        mock_git.return_value = b"diff --git a/auth.py b/auth.py\n--- a/auth.py\n+++ b/auth.py\n@@ -5,1 +5,1 @@\n-# todo\n+# updated auth comments"
        
        # LLM returns failed JSON identifying the hallucination
        mock_query.return_value = (
            '{"passed": false, "hallucinations": ["Claims implementation of secure_vault.get_rsa_keys() but diff shows only comments modified"]}',
            "ollama",
            {}
        )
        
        res = run_contrastive_validation(content_l4)
        self.assertFalse(res)
        mock_query.assert_called_once()

    @patch("subprocess.check_output")
    @patch("lib.llm_client.query_llm_safe")
    def test_offline_fallback_passes_resiliently(self, mock_query, mock_git):
        # L3 response
        content_l3 = (
            "🤖 Flow: **[L3]** | 🧠 Model: gemini-3.1-pro-high\n"
            "🎯 **Context/Goal**: Refactor authentication handler.\n"
            "📂 **Impacted Components**: file:///auth.py\n"
        )
        
        mock_git.return_value = b"some changes"
        # LLM fails and returns stub
        mock_query.return_value = ("⚠️ [LLM Unavailable]", "stub", {})
        
        # Should return True and warning instead of raising or returning False
        res = run_contrastive_validation(content_l3)
        self.assertTrue(res)

if __name__ == "__main__":
    unittest.main()
