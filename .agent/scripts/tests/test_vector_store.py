#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import knowledge.vector_store as vector

class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_vector_store").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.storage_path = self.test_root / "memory.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_add_and_save(self):
        store = vector.SimpleVectorStore(storage_path=str(self.storage_path))
        store.add("text1", [1.0, 0.0], {"meta": "data"})
        self.assertEqual(len(store.index), 1)
        
        store.save()
        self.assertTrue(self.storage_path.exists())
        
        # Load in new store
        store2 = vector.SimpleVectorStore(storage_path=str(self.storage_path))
        self.assertEqual(len(store2.index), 1)
        self.assertEqual(store2.index[0]["text"], "text1")

    def test_cosine_similarity(self):
        store = vector.SimpleVectorStore(storage_path=str(self.storage_path))
        sim1 = store._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        self.assertAlmostEqual(sim1, 1.0)
        
        sim2 = store._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        self.assertAlmostEqual(sim2, 0.0)
        
        # Zero vector handling
        sim3 = store._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        self.assertEqual(sim3, 0.0)

    def test_search(self):
        store = vector.SimpleVectorStore(storage_path=str(self.storage_path))
        store.add("perfect", [1.0, 0.0])
        store.add("orthogonal", [0.0, 1.0])
        store.add("opposite", [-1.0, 0.0])
        
        results = store.search([1.0, 0.0], top_k=2)
        self.assertEqual(len(results), 2)
        
        # First result should be 'perfect'
        self.assertEqual(results[0][1]["text"], "perfect")
        self.assertAlmostEqual(results[0][0], 1.0)
        
        # Second should be 'orthogonal'
        self.assertEqual(results[1][1]["text"], "orthogonal")
        self.assertAlmostEqual(results[1][0], 0.0)

if __name__ == "__main__":
    unittest.main()
