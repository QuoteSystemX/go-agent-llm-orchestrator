#!/usr/bin/env python3
import unittest
import sys
import tempfile
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import dev.skill_files_retrofit as retrofit
from test_skill_files_lint import write_skill  # noqa: E402  (fixture helper, same tests dir)


class TestUpsertFilesLine(unittest.TestCase):
    def test_appends_when_absent(self):
        text = "---\nname: x\ndescription: y\n---\n\nBody."
        out = retrofit.upsert_files_line(text, "files: a.md, b.md")
        self.assertIn("files: a.md, b.md", out)
        # Body must survive untouched.
        self.assertTrue(out.endswith("\n\nBody."))
        # Frontmatter still closes properly.
        self.assertEqual(out.count("---"), 2)

    def test_replaces_when_present(self):
        text = "---\nname: x\nfiles: old.md\ndescription: y\n---\n\nBody."
        out = retrofit.upsert_files_line(text, "files: new.md, other.md")
        self.assertIn("files: new.md, other.md", out)
        self.assertNotIn("old.md", out)
        # Other frontmatter lines and their order survive.
        self.assertIn("name: x", out)
        self.assertIn("description: y", out)


class TestProcessSkill(unittest.TestCase):
    def test_seeds_when_files_present_and_field_absent(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(Path(td), "needs-seed", files={"a.md": "x", "scripts/b.py": "y"})
            result = retrofit.process_skill(skill_dir, force=False, dry_run=False)
            self.assertEqual(result, "seeded")
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("files: a.md, scripts/b.py", text)

    def test_skips_when_no_sibling_files(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(Path(td), "solo")
            result = retrofit.process_skill(skill_dir, force=False, dry_run=False)
            self.assertEqual(result, "skipped-no-files")
            self.assertNotIn("files:", (skill_dir / "SKILL.md").read_text(encoding="utf-8"))

    def test_skips_when_already_set_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(
                Path(td), "already-set",
                frontmatter_extra="files: a.md\n",
                files={"a.md": "x", "b.md": "y"},  # b.md deliberately not declared
            )
            result = retrofit.process_skill(skill_dir, force=False, dry_run=False)
            self.assertEqual(result, "skipped-already-set")
            # Untouched — retrofit never silently expands a hand-curated list.
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("files: a.md\n", text)
            self.assertNotIn("b.md", text)

    def test_force_reseeds_existing(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(
                Path(td), "reseed-me",
                frontmatter_extra="files: stale.md\n",
                files={"a.md": "x"},
            )
            result = retrofit.process_skill(skill_dir, force=True, dry_run=False)
            self.assertEqual(result, "seeded")
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("files: a.md", text)
            self.assertNotIn("stale.md", text)

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(Path(td), "dry-run-me", files={"a.md": "x"})
            before = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            result = retrofit.process_skill(skill_dir, force=False, dry_run=True)
            self.assertEqual(result, "seeded")
            after = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
