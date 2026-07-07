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

from lib.llm_client import call_mcp_broker, query_llm_safe

class TestMCPLlmBroker(unittest.TestCase):
    
    @patch('subprocess.run')
    def test_call_mcp_broker_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        
        response_data = {
            "response": "Hello world from Go!",
            "source": "ollama",
            "model": "qwen2.5-coder:14b",
            "stats": {"cached": False}
        }
        mock_proc.stdout = json.dumps(response_data)
        mock_run.return_value = mock_proc
        
        res = call_mcp_broker("execute_prompt", {"prompt": "hello"})
        self.assertEqual(res["response"], "Hello world from Go!")
        self.assertEqual(res["source"], "ollama")
        self.assertEqual(res["model"], "qwen2.5-coder:14b")

    @patch('lib.llm_client.call_mcp_broker')
    def test_query_llm_safe_success(self, mock_call):
        mock_call.return_value = {
            "response": "Success!",
            "source": "antigravity",
            "model": "gemini-3-flash",
            "stats": {"cached": True}
        }
        
        text, source, stats = query_llm_safe("test prompt")
        self.assertEqual(text, "Success!")
        self.assertEqual(source, "antigravity")
        self.assertEqual(stats["model"], "gemini-3-flash")
        self.assertTrue(stats["cached"])

    @patch('lib.llm_client.call_mcp_broker', side_effect=Exception("binary error"))
    def test_query_llm_safe_fallback_to_stub(self, mock_call):
        text, source, stats = query_llm_safe("test prompt", default_model="stub-model")
        self.assertTrue(text.startswith("⚠️ [LLM Unavailable]"))
        self.assertEqual(source, "stub")
        self.assertEqual(stats["model"], "stub-model")

if __name__ == "__main__":
    unittest.main()
