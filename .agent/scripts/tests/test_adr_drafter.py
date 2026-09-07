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

import knowledge.adr_drafter as drafter

class TestADRDrafter(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_adr_drafter").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.adr_dir = self.test_root / "wiki" / "decisions"
        self.adr_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_adr_dir = patch('knowledge.adr_drafter.ADR_DIR', self.adr_dir)
        self.patch_workspace = patch('knowledge.adr_drafter.WORKSPACE_ROOT', self.test_root)
        self.patch_adr_dir.start()
        self.patch_workspace.start()

    def tearDown(self):
        self.patch_adr_dir.stop()
        self.patch_workspace.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_draft_adr_detection(self):
        # Create a trigger file
        shared_ui_dir = self.test_root / "paperclip-plugin" / "src" / "ui" / "components" / "shared"
        shared_ui_dir.mkdir(parents=True)
        (shared_ui_dir / "Button.tsx").write_text("// Shared button")
        
        result = drafter.draft_adr()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["count"], 1)
        
        # Verify file content
        draft_file = Path(result["drafted_adrs"][0])
        self.assertTrue(draft_file.exists())
        content = draft_file.read_text()
        self.assertIn("# ADR-001: Standardization of UI Component System", content)
        self.assertIn("DRAFT (Proposed by Archivist)", content)

    def test_draft_adr_id_increment(self):
        # Pre-create an unrelated ADR (not one of the two hardcoded titles below, so it only
        # exercises the id-increment path, not the skip-if-already-drafted path)
        (self.adr_dir / "ADR-001-existing.md").write_text("existing")
        
        # Create triggers
        go_handler_dir = self.test_root / ".agent" / "mcp-server-agent-kit"
        go_handler_dir.mkdir(parents=True)
        (go_handler_dir / "handler.go").write_text("package main")
        
        result = drafter.draft_adr()
        self.assertEqual(result["count"], 1)
        self.assertIn("ADR-002", result["drafted_adrs"][0])

    def test_no_triggers(self):
        result = drafter.draft_adr()
        self.assertEqual(result["count"], 0)

    def test_skips_redraft_of_existing_decision(self):
        # The exact bug this fix closes: re-running with the same trigger present must not
        # draft a second copy of a decision that already exists under some other id.
        (self.adr_dir / "ADR-005-standardization-of-ui-component-system.md").write_text("existing")

        shared_ui_dir = self.test_root / "paperclip-plugin" / "src" / "ui" / "components" / "shared"
        shared_ui_dir.mkdir(parents=True)
        (shared_ui_dir / "Button.tsx").write_text("// Shared button")

        result = drafter.draft_adr()
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["drafted_adrs"], [])

    def test_does_not_false_positive_on_slug_substring(self):
        # A filename whose slug merely CONTAINS the target slug as a substring (but isn't an
        # exact match) must not block drafting the real decision — found in review: an unanchored
        # `slug in f.name` check would wrongly treat "re-adoption-of-mcp-go-server-framework-v2"
        # as covering "adoption-of-mcp-go-server-framework".
        (self.adr_dir / "ADR-009-re-adoption-of-mcp-go-server-framework-v2.md").write_text("unrelated")

        go_handler_dir = self.test_root / ".agent" / "mcp-server-agent-kit"
        go_handler_dir.mkdir(parents=True)
        (go_handler_dir / "handler.go").write_text("package main")

        result = drafter.draft_adr()
        self.assertEqual(result["count"], 1)
        self.assertIn("ADR-010-adoption-of-mcp-go-server-framework.md", result["drafted_adrs"][0])

if __name__ == "__main__":
    unittest.main()
