#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import models.embedding_client as embed

class TestEmbeddingClient(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_get_embedding_success(self, mock_urlopen):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        client = embed.OllamaEmbeddingClient()
        result = client.get_embedding("test text")
        
        self.assertEqual(result, [0.1, 0.2, 0.3])
        # Verify request parameters
        args, kwargs = mock_urlopen.call_args
        request = args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "http://localhost:11434/api/embeddings")
        
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload["prompt"], "test text")
        self.assertEqual(payload["model"], "mxbai-embed-large")

    @patch('urllib.request.urlopen')
    def test_get_embedding_error(self, mock_urlopen):
        # Mock URL error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        client = embed.OllamaEmbeddingClient()
        with patch('sys.stdout', new=MagicMock()):
            result = client.get_embedding("test text")
            
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
