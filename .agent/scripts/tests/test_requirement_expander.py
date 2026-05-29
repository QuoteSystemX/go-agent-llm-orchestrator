#!/usr/bin/env python3
import unittest
import json
import shutil
import sys
import os
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

import analysis.requirement_expander as expander

_STUB_LLM_ANSWER = "RFC 7807: Use standard Problem Details for HTTP APIs."


class TestRequirementExpander(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_expander"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.config_path = self.test_root / ".agent" / "config" / "gateway_config.json"
        self.config_path.parent.mkdir(parents=True)
        
        self.patch_config = patch('analysis.requirement_expander.CONFIG_PATH', self.config_path)
        self.patch_config.start()

    def tearDown(self):
        self.patch_config.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('analysis.requirement_expander._search_standards',
           return_value=["[LOCAL_GLOBAL_BRAIN] standards/api_guidelines.md: Use RFC 7807"])
    @patch('sys.stdout', new_callable=MagicMock)
    def test_expand_requirements_api(self, mock_stdout, mock_search):
        expander.expand_requirements("build api")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("[LOCAL_GLOBAL_BRAIN]", output)
        self.assertIn("RFC 7807", output)

    @patch('analysis.requirement_expander._query_llm_safe',
           return_value=_STUB_LLM_ANSWER)
    @patch('sys.stdout', new_callable=MagicMock)
    def test_expand_requirements_cache_with_mcp(self, mock_stdout, mock_llm):
        config = {
            "gateway": {
                "ranking_protocol": ["specialized_mcp"],
                "mcp_servers": {"github": {"enabled": True}}
            }
        }
        self.config_path.write_text(json.dumps(config))
        
        expander.expand_requirements("setup cache")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("[SPECIALIZED_MCP]", output)

    @patch('analysis.requirement_expander._query_llm_safe',
           return_value=_STUB_LLM_ANSWER)
    @patch('sys.stdout', new_callable=MagicMock)
    def test_expand_requirements_web_fallback(self, mock_stdout, mock_llm):
        config = {"gateway": {"ranking_protocol": ["general_web_search"]}}
        self.config_path.write_text(json.dumps(config))
        
        expander.expand_requirements("random task")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("[GENERAL_WEB_SEARCH]", output)

    @patch('analysis.requirement_expander._search_standards',
           return_value=["[LOCAL_GLOBAL_BRAIN] standards/api.md: Use RFC 7807"])
    @patch('sys.stdout', new_callable=MagicMock)
    def test_expand_requirements_with_feedback(self, mock_stdout, mock_search):
        expander.expand_requirements("api", feedback="security")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Re-expanding requirements based on feedback: 'security'", output)

if __name__ == "__main__":
    unittest.main()
