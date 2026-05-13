#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
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

import knowledge.knowledge_miner as miner

class TestKnowledgeMiner(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_miner").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.wiki_map = self.bus_dir / "wiki_map.json"
        
        self.wiki_dir = self.test_root / "wiki" / "mental-models"
        self.proposals_dir = self.test_root / "wiki" / "proposals"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_map = patch('knowledge.knowledge_miner.WIKI_MAP', self.wiki_map)
        self.patch_models = patch('knowledge.knowledge_miner.WIKI_DIR', self.wiki_dir)
        self.patch_proposals = patch('knowledge.knowledge_miner.PROPOSALS_DIR', self.proposals_dir)
        self.patch_map.start()
        self.patch_models.start()
        self.patch_proposals.start()

    def tearDown(self):
        self.patch_map.stop()
        self.patch_models.stop()
        self.patch_proposals.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_get_undocumented_files(self):
        # Create some files
        (self.test_root / "pkg").mkdir()
        (self.test_root / "pkg" / "a.py").write_text("# a")
        (self.test_root / "pkg" / "b.py").write_text("# b")
        (self.test_root / "root.py").write_text("# root")
        
        # Mock wiki map
        wiki_map = {
            "map": {
                "Root": {"resolved_code_paths": ["root.py"]}
            }
        }
        
        undocumented = miner.get_undocumented_files(wiki_map)
        self.assertIn("pkg/a.py", undocumented)
        self.assertIn("pkg/b.py", undocumented)
        self.assertNotIn("root.py", undocumented)

    def test_propose_mental_model(self):
        undocumented = ["pkg/a.py", "pkg/b.py", "other/c.py"]
        proposals = miner.propose_mental_model(undocumented)
        
        # Should only group clusters (2+ files)
        self.assertEqual(len(proposals), 1)
        self.assertIn("PROPOSAL-Pkg.md", proposals[0])
        
        prop_file = Path(proposals[0])
        self.assertTrue(prop_file.exists())
        content = prop_file.read_text()
        self.assertIn("a.py", content)
        self.assertIn("b.py", content)

    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_audit(self, mock_stdout):
        # Setup files and map
        (self.test_root / "pkg").mkdir()
        (self.test_root / "pkg" / "a.py").write_text("# a")
        (self.test_root / "pkg" / "b.py").write_text("# b")
        self.wiki_map.write_text(json.dumps({"map": {}}))
        
        miner.run_audit()
        
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("Found 2 undocumented files", output)
        self.assertIn("Generated 1 Mental Model proposals", output)

if __name__ == "__main__":
    unittest.main()
