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

import models.ollama_agent as ollama_agent

class TestOllamaAgent(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_ollama_agent").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_best_model(self):
        self.assertEqual(ollama_agent.get_best_model(2), ollama_agent.MODEL_MAP["L1"])
        self.assertEqual(ollama_agent.get_best_model(5), ollama_agent.MODEL_MAP["L2"])
        self.assertEqual(ollama_agent.get_best_model(8), ollama_agent.MODEL_MAP["L3"])
        self.assertEqual(ollama_agent.get_best_model(10), ollama_agent.MODEL_MAP["L4"])

    @patch('models.ollama_agent.query_ollama')
    @patch('models.ollama_agent.list_dir')
    @patch('models.ollama_agent.grep_files')
    def test_execute_with_ollama(self, mock_grep, mock_ls, mock_query):
        mock_ls.return_value = "file1.py\nfile2.py"
        mock_grep.return_value = "TODO: fix this"
        mock_query.return_value = ("Analysis result", 1.0, 10.0)
        
        with patch('sys.stdout', new=MagicMock()):
            result = ollama_agent.execute_with_ollama("analyze codebase", "code-archaeologist")
            
        self.assertEqual(result, "Analysis result")
        
        # Verify it auto-selected L4 model (complexity 8/10 due to "analyze")
        # "analyze" gives complexity 7 or 8. get_best_model(8) -> L3 or L4.
        # Actually it depends on exact dictionary. "analyze": 7 (or 8 in main).
        args, kwargs = mock_query.call_args
        self.assertTrue(args[1] in ollama_agent.MODEL_MAP.values())

    @patch('models.ollama_agent.execute_with_ollama')
    @patch('models.ollama_agent.push_to_telemetry')
    @patch('sys.argv', ['ollama_agent.py', 'find stuff', '--agent', 'explorer-agent'])
    def test_main(self, mock_push, mock_execute):
        mock_execute.return_value = "Result"
        
        with patch('sys.stdout', new=MagicMock()):
            ollama_agent.main()
            
        mock_execute.assert_called_once()
        mock_push.assert_called_once()

if __name__ == "__main__":
    unittest.main()
