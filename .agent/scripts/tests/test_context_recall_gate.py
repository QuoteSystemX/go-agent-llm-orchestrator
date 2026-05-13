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

import context.context_recall_gate as recall

class TestContextRecallGate(unittest.TestCase):
    @patch('context.context_recall_gate.OllamaEmbeddingClient')
    @patch('context.context_recall_gate.SimpleVectorStore')
    @patch('semantic_context_optimizer.optimize_context', side_effect=lambda x: x)
    def test_recall_context_success(self, mock_opt, mock_store, mock_client):
        # Mock client
        mock_client.return_value.get_embedding.return_value = [0.1, 0.2]
        
        # Mock store
        store_instance = mock_store.return_value
        store_instance.index = True
        store_instance.search.return_value = [
            (0.9, {"text": "Past decision A", "metadata": {"source": "wiki/adr-001.md"}})
        ]
        
        result = recall.recall_context("how to handle auth?")
        self.assertIn("AOS NEURAL RECALL", result)
        self.assertIn("Past decision A", result)
        self.assertIn("wiki/adr-001.md", result)

    @patch('context.context_recall_gate.SimpleVectorStore')
    def test_recall_context_empty(self, mock_store):
        mock_store.return_value.index = False
        result = recall.recall_context("test")
        self.assertIn("No memory entries found", result)

    @patch('context.context_recall_gate.OllamaEmbeddingClient')
    @patch('context.context_recall_gate.SimpleVectorStore')
    def test_recall_context_embedding_error(self, mock_store, mock_client):
        mock_store.return_value.index = True
        mock_client.return_value.get_embedding.return_value = None
        result = recall.recall_context("test")
        self.assertIn("Error: Could not generate embedding", result)

if __name__ == "__main__":
    unittest.main()
