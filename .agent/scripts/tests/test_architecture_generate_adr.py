#!/usr/bin/env python3
"""Tests for .agent/skills/architecture/scripts/generate_adr.py.

Not to be confused with .agent/scripts/knowledge/generate_adr.py, which has
its own test_generate_adr.py — the two are unrelated scripts that happen to
share a filename.
"""
import importlib.util
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

SCRIPT_PATH = REPO_ROOT / ".agent" / "skills" / "architecture" / "scripts" / "generate_adr.py"
spec = importlib.util.spec_from_file_location("architecture_generate_adr", SCRIPT_PATH)
generate_adr_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_adr_module)


class TestArchitectureGenerateAdr(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_architecture_generate_adr").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

        self.adr_dir = self.test_root / "wiki" / "decisions"
        self.adr_dir.mkdir(parents=True)

        self.patch_adr_dir = patch.object(generate_adr_module, "ADR_DIR", self.adr_dir)
        self.patch_adr_dir.start()

    def tearDown(self):
        self.patch_adr_dir.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_slugify_strips_punctuation_and_case(self):
        self.assertEqual(
            generate_adr_module.slugify("Fix: use A/B testing!"),
            "fix-use-a-b-testing",
        )

    def test_slugify_empty_title_falls_back(self):
        self.assertEqual(generate_adr_module.slugify("---"), "untitled")

    def test_next_adr_id_uses_max_not_count(self):
        # A deleted/renumbered file (ADR-002 missing) must not undercount.
        (self.adr_dir / "ADR-001-first.md").write_text("x")
        (self.adr_dir / "ADR-007-seventh.md").write_text("x")
        (self.adr_dir / "not-an-adr.md").write_text("x")
        self.assertEqual(generate_adr_module.next_adr_id(), 8)

    def test_next_adr_id_empty_dir_starts_at_one(self):
        self.assertEqual(generate_adr_module.next_adr_id(), 1)

    def test_generate_adr_writes_uppercase_prefixed_file(self):
        generate_adr_module.generate_adr("My Cool Decision")
        expected = self.adr_dir / "ADR-001-my-cool-decision.md"
        self.assertTrue(expected.exists())
        self.assertIn("# ADR-001: My Cool Decision", expected.read_text())

    def test_generate_adr_skips_past_a_stale_filename_collision(self):
        # Simulates next_adr_id() racing another writer: id 1 is handed out,
        # but ADR-001-my-cool-decision.md already exists by the time we write.
        (self.adr_dir / "ADR-001-my-cool-decision.md").write_text("existing")
        with patch.object(generate_adr_module, "next_adr_id", return_value=1):
            generate_adr_module.generate_adr("My Cool Decision")
        self.assertTrue((self.adr_dir / "ADR-002-my-cool-decision.md").exists())
        self.assertEqual(
            (self.adr_dir / "ADR-001-my-cool-decision.md").read_text(), "existing"
        )


if __name__ == "__main__":
    unittest.main()
