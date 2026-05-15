#!/usr/bin/env python3
"""Tests for obsidian_validator.py (new CLI-based API)."""
import unittest
import shutil
import sys
import os
import json
import importlib.util
from pathlib import Path
from io import StringIO

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

# Import the validator module directly to test internals
sys.path.insert(0, str(REPO_ROOT / ".agent" / "scripts"))
import importlib
spec = importlib.util.spec_from_file_location(
    "obsidian_validator_module",
    str(REPO_ROOT / ".agent" / "scripts" / "knowledge" / "obsidian_validator.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

Validator = mod.Validator
ValidationResult = mod.ValidationResult
Repairer = mod.Repairer
Migrator = mod.Migrator
VaultDetector = mod.VaultDetector


class TestValidatorInternals(unittest.TestCase):
    """Test core validation logic directly."""

    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_obsidian_validator").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

        self.vault = self.test_root / "wiki"
        self.vault.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def _write(self, name: str, content: str):
        (self.vault / name).write_text(content)

    def test_broken_links_detected(self):
        self._write("Source.md", "Check [[MissingFile]] and [[Target]].")
        self._write("Target.md", "Hello.")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(len(result.broken_links), 1)
        self.assertEqual(result.broken_links[0][1], "MissingFile")

    def test_broken_links_with_md_extension(self):
        """Links with .md extension should be handled correctly."""
        self._write("Source.md", "Check [[MissingFile.md]].")
        self._write("Target.md", "Hello.")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(len(result.broken_links), 1)
        self.assertEqual(result.broken_links[0][1], "MissingFile.md")

    def test_orphans_detected(self):
        self._write("Source.md", "Hello.")
        self._write("Orphan.md", "No links to me.")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertIn("Orphan", result.orphans)

    def test_no_orphan_for_linked_file(self):
        self._write("Source.md", "Link to [[Target]].")
        self._write("Target.md", "Linked!")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertNotIn("Target", result.orphans)

    def test_missing_frontmatter_detected(self):
        self._write("NoFrontmatter.md", "# Just content")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(len(result.missing_frontmatter), 1)
        self.assertIn("title", result.missing_frontmatter[0][1])

    def test_complete_frontmatter_ok(self):
        self._write("Good.md", "---\ntitle: Test\ntags:\n  - test\nstatus: active\n---\n# Content")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(len(result.missing_frontmatter), 0)

    def test_clean_vault(self):
        # Two files linking to each other = no orphans
        self._write("Note.md", "---\ntitle: Note\ntags:\n  - test\nstatus: active\n---\n# Note\n\nSee also [[Index]].")
        self._write("Index.md", "---\ntitle: Index\ntags:\n  - test\nstatus: active\n---\n# Index\n\nSee [[Note]] for details.")
        validator = Validator(self.vault)
        result = validator.validate_all()
        if not result.is_clean:
            print(f"  Debug - orphans: {result.orphans}, broken: {result.broken_links[:2]}, fm: {result.missing_frontmatter[:2]}")
        self.assertTrue(result.is_clean)

    def test_compliance_pct(self):
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(result.compliance_pct, 100.0)


class TestRepairer(unittest.TestCase):
    """Test auto-fix logic."""

    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_obsidian_validator_repair").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.vault = self.test_root / "wiki"
        self.vault.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_fix_broken_links_creates_stubs(self):
        (self.vault / "Source.md").write_text("Link to [[MissingTarget]].")
        validator = Validator(self.vault)
        result = validator.validate_all()
        self.assertEqual(len(result.broken_links), 1)

        repairer = Repairer(self.vault, dry_run=False)
        fixed = repairer.fix_broken_links(result)
        self.assertEqual(fixed, 1)
        self.assertTrue((self.vault / "MissingTarget.md").exists())

    def test_fix_does_not_create_double_ext(self):
        """Stub creation should handle targets with .md in name."""
        (self.vault / "Source.md").write_text("Link to [[SomeFile.md]].")
        validator = Validator(self.vault)
        result = validator.validate_all()

        repairer = Repairer(self.vault, dry_run=False)
        fixed = repairer.fix_broken_links(result)
        self.assertEqual(fixed, 1)
        # Should create SomeFile.md NOT SomeFile.md.md
        self.assertTrue((self.vault / "SomeFile.md").exists())
        self.assertFalse((self.vault / "SomeFile.md.md").exists())

    def test_add_frontmatter(self):
        (self.vault / "Note.md").write_text("# Bare content")
        validator = Validator(self.vault)
        result = validator.validate_all()

        repairer = Repairer(self.vault, dry_run=False)
        fixed = repairer.add_frontmatter(result)
        self.assertEqual(fixed, 1)

        # Verify frontmatter was added
        content = (self.vault / "Note.md").read_text()
        self.assertIn("---", content)
        self.assertIn("title:", content)
        self.assertIn("tags:", content)


class TestMigrator(unittest.TestCase):
    """Test vault initialization and merge."""

    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_obsidian_validator_migrate").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_init_vault_creates_structure(self):
        vault = self.test_root / "wiki"
        migrator = Migrator(vault, dry_run=False)
        created = migrator.init_vault()
        self.assertTrue(vault.exists())
        self.assertTrue((vault / "_index.md").exists())
        self.assertEqual(created, 3)  # vault dir + .obsidian + _index.md

    def test_merge_from_other_dir(self):
        vault = self.test_root / "wiki"
        vault.mkdir()
        source = self.test_root / "docs"
        source.mkdir()
        (source / "doc1.md").write_text("# Doc 1")
        (source / "doc2.md").write_text("# Doc 2")

        migrator = Migrator(vault, dry_run=False)
        moved = migrator.merge_from(source)
        self.assertEqual(moved, 2)
        self.assertTrue((vault / "doc1.md").exists())
        self.assertTrue((vault / "doc2.md").exists())

    def test_merge_dry_run(self):
        vault = self.test_root / "wiki"
        vault.mkdir()
        source = self.test_root / "docs"
        source.mkdir()
        (source / "doc1.md").write_text("# Doc 1")

        migrator = Migrator(vault, dry_run=True)
        moved = migrator.merge_from(source)
        self.assertEqual(moved, 1)
        self.assertFalse((vault / "doc1.md").exists())


class TestVaultDetector(unittest.TestCase):
    """Test vault and documentation directory detection."""

    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_vault_detector").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_find_no_vault(self):
        detector = VaultDetector(self.test_root)
        self.assertIsNone(detector.find_vault())

    def test_find_vault(self):
        wiki_dir = self.test_root / "wiki"
        wiki_dir.mkdir()
        detector = VaultDetector(self.test_root)
        self.assertIsNotNone(detector.find_vault())

    def test_find_doc_dirs(self):
        (self.test_root / "docs").mkdir()
        (self.test_root / "docs" / "readme.md").write_text("# Docs")
        (self.test_root / "wiki").mkdir()
        (self.test_root / "wiki" / "note.md").write_text("# Note")

        detector = VaultDetector(self.test_root)
        doc_dirs = detector.find_doc_dirs()
        names = [d.name for d in doc_dirs]
        self.assertIn("docs", names)
        self.assertIn("wiki", names)


if __name__ == "__main__":
    unittest.main()
