#!/usr/bin/env python3
import unittest
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.agent_auctioneer as auctioneer

class TestAgentAuctioneer(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_auctioneer"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.agents_dir = self.test_root / ".agent" / "agents"
        self.agents_dir.mkdir(parents=True)
        
        self.patch_repo = patch('orchestration.agent_auctioneer.REPO_ROOT', self.test_root)
        self.patch_repo.start()

    def tearDown(self):
        self.patch_repo.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_parse_frontmatter(self):
        content = "---\ndomains: go, testing\nskills: unit-test\n---\nBody"
        fm, body = auctioneer.parse_frontmatter(content)
        self.assertEqual(fm["domains"], "go, testing")
        self.assertEqual(fm["skills"], "unit-test")
        self.assertEqual(body.strip(), "Body")

    def test_load_matrix(self):
        agent_file = self.agents_dir / "tester.md"
        agent_file.write_text("---\ndomains: testing\nskills: pytest\ndescription: Test agent\n---")
        
        with patch('orchestration.agent_auctioneer.Path', return_value=self.agents_dir):
            matrix = auctioneer.load_matrix()
            self.assertEqual(len(matrix["agents"]), 1)
            self.assertEqual(matrix["agents"][0]["id"], "tester")
            self.assertIn("testing", matrix["agents"][0]["domains"])

    def test_find_candidates_scoring(self):
        # Mock load_matrix to return controlled agents
        mock_matrix = {
            "agents": [
                {"id": "go-dev", "domains": ["go"], "skills": ["go-patterns"], "description": "Go expert"},
                {"id": "tester", "domains": ["testing"], "skills": ["unit-test"], "description": "QA expert"}
            ]
        }
        with patch('orchestration.agent_auctioneer.load_matrix', return_value=mock_matrix):
            # Test domain match
            candidates = auctioneer.find_candidates("fix go bug")
            self.assertEqual(candidates[0]["id"], "go-dev")
            self.assertEqual(candidates[0]["score"], 1) # 1 domain
            
            # Test skill match
            candidates = auctioneer.find_candidates("write unit-test")
            self.assertEqual(candidates[0]["id"], "tester")
            self.assertEqual(candidates[0]["score"], 2) # 2 skills
            
            # Test identity match
            candidates = auctioneer.find_candidates("use go-dev for this")
            self.assertEqual(candidates[0]["id"], "go-dev")
            self.assertEqual(candidates[0]["score"], 4) # 3 identity + 1 domain

    def test_run_auction_winner(self):
        mock_matrix = {"agents": [{"id": "winner", "domains": ["win"], "skills": [], "description": "d"}]}
        with patch('orchestration.agent_auctioneer.load_matrix', return_value=mock_matrix):
            res = auctioneer.run_auction("s1", "role1", "task win")
            self.assertEqual(res["id"], "winner")
            self.assertEqual(res["status"], "assigned_via_auction")

    def test_run_auction_fallback(self):
        with patch('orchestration.agent_auctioneer.load_matrix', return_value={"agents": []}):
            res = auctioneer.run_auction("s1", "role1", "unknown task")
            self.assertEqual(res["id"], "orchestrator")
            self.assertEqual(res["status"], "assigned_fallback")

    def test_run_auction_arena(self):
        mock_matrix = {
            "agents": [
                {"id": "a1", "domains": ["x"], "skills": [], "description": "d"},
                {"id": "a2", "domains": ["x"], "skills": [], "description": "d"}
            ]
        }
        with patch('orchestration.agent_auctioneer.load_matrix', return_value=mock_matrix):
            res = auctioneer.run_auction("s1", "role1", "task x")
            self.assertEqual(res["id"], "PENDING_ARENA")
            self.assertIn("a1", res["candidates"])
            self.assertIn("a2", res["candidates"])

if __name__ == "__main__":
    unittest.main()
