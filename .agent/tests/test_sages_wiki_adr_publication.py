#!/usr/bin/env python3
import unittest
import unittest.mock
import shutil
import sys
import os
import json
from pathlib import Path

# Antigravity Domain-Aware Import Logic
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

class TestSagesWikiAdrPublication(unittest.TestCase):
    def setUp(self):
        # Create an isolated environment in scratch/test_wiki_adr
        self.test_root = (REPO_ROOT / "scratch" / "test_wiki_adr").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        self.bus_file = self.bus_dir / "context.json"

        self.wiki_dir = self.test_root / "wiki"
        self.decisions_dir = self.wiki_dir / "decisions"
        self.decisions_dir.mkdir(parents=True)

        self.fragments_dir = self.wiki_dir / "fragments" / "core"
        self.fragments_dir.mkdir(parents=True)

        # Create basic files needed for wiki sync/assembly
        self.decisions_fragment = self.fragments_dir / "07-recent-decisions.md"
        self.decisions_fragment.write_text("---\ntitle: \"07 Recent Decisions\"\n---\n\n")

        self.component_fragment = self.fragments_dir / "04-component-map.md"
        self.component_fragment.write_text("# Component Map\n├── scripts/\n")

        self.arch_template = self.wiki_dir / "ARCHITECTURE.template.md"
        self.arch_template.write_text("# System Architecture\n\n<!-- @INJECT:core/07-recent-decisions -->\n\n<!-- @INJECT:core/04-component-map -->\n")

        # Mock templates dir
        self.templates_dir = self.test_root / ".agent" / "wiki-templates"
        self.templates_dir.mkdir(parents=True)
        self.decisions_template = self.templates_dir / "DECISIONS.md"
        self.decisions_template.write_text("## ADR-001: [Decision Title]\n- **Date:** YYYY-MM-DD\n- **Status:** Proposed\n")

        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_expert_debate_auto_publication(self):
        print("🧪 Testing expert debate ADR auto-publication...")

        # 1. Create a mock verification_result payload (Expert debate format)
        mock_verdict = {
            "status": "approved",
            "confidence": 0.95,
            "summary": "Implement isolated session orchestration directory structure.",
            "conditions": ["Verify cleanup logic runs on failure."],
            "risk_areas": ["Session ID propagation overhead."]
        }
        mock_critiques = {
            "critiques": [
                {
                    "id": "CRIT-001",
                    "category": "security",
                    "severity": "blocker",
                    "description": "Shared directory access creates data leakage risks.",
                    "suggested_action": "Isolate paths using session UUIDs."
                }
            ]
        }
        mock_resolutions = {
            "resolutions": [
                {
                    "critique_id": "CRIT-001",
                    "accepted": True,
                    "resolution": "All active session variables are stored strictly in unique UUID subfolders."
                }
            ]
        }

        bus_payload = {
            "version": "1.0.0",
            "objects": [
                {
                    "id": "verdict_test_session_sharding",
                    "type": "verification_result",
                    "author": "arbitrator",
                    "timestamp": "2026-05-28T12:00:00Z",
                    "content": {
                        "plan_id": "test_session_sharding",
                        "title": "Session-Based Orchestration Sharding",
                        "verdict": mock_verdict,
                        "critiques": mock_critiques,
                        "resolutions": mock_resolutions,
                        "debate_type": "expert"
                    }
                }
            ]
        }
        self.bus_file.write_text(json.dumps(bus_payload, indent=2))

        # 2. Run adr_observer.py (Import and call)
        # We will dynamically mock REPO_ROOT and Path targets in adr_observer
        sys.path.insert(0, str(SCRIPTS_DIR / "knowledge"))
        try:
            adr_observer = __import__("adr_observer", fromlist=["process_bus_events"])
            
            # Patch paths to point to test isolated env
            with unittest.mock.patch("adr_observer.BUS_FILE", self.bus_file), \
                 unittest.mock.patch("adr_observer.DECISIONS_DIR", self.decisions_dir), \
                 unittest.mock.patch("adr_observer.TEMPLATES_DIR", self.templates_dir), \
                 unittest.mock.patch("adr_observer.WIKI_DIR", self.wiki_dir), \
                 unittest.mock.patch("subprocess.run") as mock_run:
                
                mock_run.return_value = unittest.mock.MagicMock(returncode=0)
                # Direct call as if triggered by hook
                result = adr_observer.process_bus_events()
                self.assertTrue(result)
        except Exception as e:
            self.fail(f"Observer execution failed: {e}")

        # 3. Assert ADR file is created under wiki/decisions/
        generated_adrs = list(self.decisions_dir.glob("ADR-*.md"))
        self.assertEqual(len(generated_adrs), 1, "Should create exactly one ADR file.")
        
        adr_file = generated_adrs[0]
        self.assertIn("test-session-sharding", adr_file.name)

        adr_content = adr_file.read_text()
        self.assertIn("status: approved", adr_content)
        self.assertIn("# ADR-001: Session-Based Orchestration Sharding", adr_content)
        self.assertIn("## Context", adr_content)
        self.assertIn("## Decision", adr_content)
        self.assertIn("## Debate Log", adr_content)
        self.assertIn("CRIT-001", adr_content)
        self.assertIn("All active session variables are stored strictly in unique UUID subfolders.", adr_content)

        # 4. Assert recent-decisions.md is updated
        fragment_content = self.decisions_fragment.read_text()
        self.assertIn(f"- [{adr_file.name}](./decisions/{adr_file.name})", fragment_content)

        # 5. Assert wiki/ARCHITECTURE.md is compiled
        compiled_arch = self.wiki_dir / "ARCHITECTURE.md"
        self.assertTrue(compiled_arch.exists(), "ARCHITECTURE.md should be compiled")
        compiled_content = compiled_arch.read_text()
        self.assertIn(f"- [{adr_file.name}](./decisions/{adr_file.name})", compiled_content)

    def test_strategic_debate_auto_publication(self):
        print("🧪 Testing strategic debate ADR auto-publication...")

        # 1. Create a mock verification_result payload (Strategic debate format)
        mock_verdict = {
            "status": "approved",
            "confidence": 0.92,
            "summary": "Introduce User DNA Stylistic Personality Sync.",
            "conditions": []
        }
        mock_responses = {
            "optimist": "Greatly matches user expectations and adapts styling automatically.",
            "skeptic": "Adds overhead of reading profile from disk during each turn.",
            "user_advocate": "Veto over-engineered databases; prefer static local JSON on Context Bus."
        }

        bus_payload = {
            "version": "1.0.0",
            "objects": [
                {
                    "id": "verdict_user_dna_sync",
                    "type": "verification_result",
                    "author": "hidden_war_room",
                    "timestamp": "2026-05-28T12:05:00Z",
                    "content": {
                        "plan_id": "user_dna_sync",
                        "title": "User DNA Sync",
                        "verdict": mock_verdict,
                        "responses": mock_responses,
                        "debate_type": "strategic"
                    }
                }
            ]
        }
        self.bus_file.write_text(json.dumps(bus_payload, indent=2))

        sys.path.insert(0, str(SCRIPTS_DIR / "knowledge"))
        try:
            adr_observer = __import__("adr_observer", fromlist=["process_bus_events"])
            with unittest.mock.patch("adr_observer.BUS_FILE", self.bus_file), \
                 unittest.mock.patch("adr_observer.DECISIONS_DIR", self.decisions_dir), \
                 unittest.mock.patch("adr_observer.TEMPLATES_DIR", self.templates_dir), \
                 unittest.mock.patch("adr_observer.WIKI_DIR", self.wiki_dir), \
                 unittest.mock.patch("subprocess.run") as mock_run:
                
                mock_run.return_value = unittest.mock.MagicMock(returncode=0)
                result = adr_observer.process_bus_events()
                self.assertTrue(result)
        except Exception as e:
            self.fail(f"Observer execution failed: {e}")

        generated_adrs = list(self.decisions_dir.glob("ADR-*.md"))
        self.assertEqual(len(generated_adrs), 1)
        
        adr_content = generated_adrs[0].read_text()
        self.assertIn("# ADR-001: User DNA Sync", adr_content)
        self.assertIn("## Strategic Debate Transcript", adr_content)
        self.assertIn("**OPTIMIST**", adr_content)
        self.assertIn("**SKEPTIC**", adr_content)
        self.assertIn("**USER ADVOCATE**", adr_content)
        self.assertIn("Veto over-engineered databases", adr_content)

if __name__ == "__main__":
    unittest.main()
