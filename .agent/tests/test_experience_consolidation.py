#!/usr/bin/env python3
"""Tests for lessons decentralization and semantic consolidation."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

# Dynamic import pattern to prevent IDE warnings
def _load_modules():
    sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))
    try:
        se = __import__("models.semantic_experience", fromlist=["search_semantic"])
        ed = __import__("knowledge.experience_distiller", fromlist=["consolidate_lessons", "parse_entries"])
        return se.search_semantic, ed.consolidate_lessons, ed.parse_entries
    except ImportError:
        sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "models"))
        sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts" / "knowledge"))
        se = __import__("semantic_experience", fromlist=["search_semantic"])
        ed = __import__("experience_distiller", fromlist=["consolidate_lessons", "parse_entries"])
        return se.search_semantic, ed.consolidate_lessons, ed.parse_entries

search_semantic, consolidate_lessons, parse_entries = _load_modules()

class TestExperienceConsolidation(unittest.TestCase):

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.read_text")
    def test_search_semantic_scans_all_locations(self, mock_read, mock_glob, mock_rglob, mock_exists):
        # Mock paths existence
        mock_exists.return_value = True
        
        # Mock files lists
        mock_rglob.return_value = [Path("skills/go-patterns/LESSONS.md")]
        mock_glob.return_value = [Path("wiki/archive/experience/2026-04-28.md")]
        
        # Mock file contents
        def fake_read(encoding="utf-8"):
            return "### [2026-05-23] [SECURITY] [go-patterns] Safe String Concatenation in Go\n- Context: ...\n"
            
        mock_read.side_effect = fake_read

        res = search_semantic("Go concatenation")
        self.assertIn("Best Contextual Match", res)
        self.assertIn("Safe String Concatenation in Go", res)

    @patch("knowledge.experience_distiller.REPO_ROOT")
    @patch("lib.llm_client.query_llm_safe")
    def test_consolidate_lessons_performs_merge(self, mock_query, mock_repo):
        # Mock repo structure
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.name = "LESSONS_LEARNED.md"
        mock_file.read_text.return_value = (
            "# Header\n\n"
            "### [2026-05-23] [BUG] [shared-context] Task 1\n- Context: Task 1 context.\n\n"
            "### [2026-05-24] [BUG] [shared-context] Task 2 (Duplicate)\n- Context: Task 2 context.\n"
        )
        
        mock_repo.glob.return_value = []
        mock_repo.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
        
        # Stub the distiller path resolution
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.rglob", return_value=[]), \
             patch("pathlib.Path.read_text", return_value=mock_file.read_text.return_value):
            
            # Mock LLM return value (consolidated 0 and 1)
            llm_json = {
                "consolidated_indexes": [[0, 1]],
                "merged_entries": ["### [2026-05-24] [BUG] [shared-context] Merged Task\n- Context: Merged context.\n"]
            }
            mock_query.return_value = (json.dumps(llm_json), "ollama", {})

            # Mock file writing
            mock_open = MagicMock()
            with patch("builtins.open", mock_open):
                res = consolidate_lessons()
                self.assertIn("Consolidation complete", res)
                mock_open.assert_called_once()

if __name__ == "__main__":
    unittest.main()
