#!/usr/bin/env python3
import unittest
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

import knowledge.memory_ingestor as ingestor

class TestMemoryIngestor(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_memory_ingestor").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.wiki_dir = self.test_root / "wiki"
        self.wiki_dir.mkdir(parents=True)
        
        self.adr_dir = self.test_root / "docs" / "adr"
        self.adr_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_chunk_text(self):
        text = "Paragraph 1.\n\nParagraph 2."
        chunks = ingestor.chunk_text(text, max_chars=15)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], "Paragraph 1.")
        self.assertEqual(chunks[1], "Paragraph 2.")

    @patch('knowledge.memory_ingestor.OllamaEmbeddingClient')
    @patch('knowledge.memory_ingestor.SimpleVectorStore')
    @patch('knowledge.memory_ingestor.Path')
    def test_ingest_docs(self, mock_path, mock_store, mock_client):
        # We want to mock the repo_root Path inside ingest_docs
        # But `Path(__file__)` is hard to mock correctly without breaking Path entirely.
        # Let's just mock the specific paths it creates.
        pass

    @patch('knowledge.memory_ingestor.OllamaEmbeddingClient')
    @patch('knowledge.memory_ingestor.SimpleVectorStore')
    def test_ingest_docs_real(self, mock_store, mock_client):
        # We need to monkey-patch Path locally or just mock the paths list
        (self.wiki_dir / "test1.md").write_text("Hello World")
        (self.adr_dir / "test2.md").write_text("Hello ADR")
        
        mock_client.return_value.get_embedding.return_value = [0.1, 0.2]
        
        # Override the doc_paths generation
        original_ingest = ingestor.ingest_docs
        
        # We can just run it, but we need it to use self.test_root
        with patch.object(Path, 'resolve') as mock_resolve:
            # When Path(__file__).resolve().parents[3] is called
            mock_resolve.return_value.parents = [None, None, None, self.test_root]
            
            with patch('sys.stdout', new=MagicMock()):
                ingestor.ingest_docs()
                
        # Check store interactions
        store_instance = mock_store.return_value
        self.assertEqual(store_instance.add.call_count, 2)
        store_instance.save.assert_called_once()
        
        # Verify first call
        args, kwargs = store_instance.add.call_args_list[0]
        self.assertIn("Hello World", kwargs["text"] if "text" in kwargs else args[0])

if __name__ == "__main__":
    unittest.main()
