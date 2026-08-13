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

import dev.skill_files_lint as lint


def write_skill(root: Path, name: str, frontmatter_extra: str = "", files: dict | None = None) -> Path:
    """Create a fixture skill directory with a SKILL.md and optional sibling files."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture\n{frontmatter_extra}---\n\nBody.\n",
        encoding="utf-8",
    )
    for rel, content in (files or {}).items():
        p = skill_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return skill_dir


class TestParseFilesField(unittest.TestCase):
    def test_absent_frontmatter_field_returns_none(self):
        text = "---\nname: x\ndescription: y\n---\n\nBody."
        self.assertIsNone(lint.parse_files_field(text))

    def test_present_field_returns_raw_value(self):
        text = "---\nname: x\nfiles: a.md, b.md\n---\n\nBody."
        self.assertEqual(lint.parse_files_field(text), "a.md, b.md")

    def test_declared_paths_splits_and_trims(self):
        self.assertEqual(
            lint.declared_paths(" a.md ,b.md,  scripts/c.py "),
            ["a.md", "b.md", "scripts/c.py"],
        )

    def test_declared_paths_empty_field(self):
        self.assertEqual(lint.declared_paths(None), [])
        self.assertEqual(lint.declared_paths(""), [])


class TestDiskFiles(unittest.TestCase):
    def test_excludes_skill_md_and_junk(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(
                Path(td), "fixture-skill",
                files={
                    "real.md": "keep me",
                    "notes.md.bak": "junk",
                    "__pycache__/x.pyc": "junk",
                    "scripts/tool.py": "keep me too",
                },
            )
            found = lint.disk_files(skill_dir)
            self.assertEqual(found, {"real.md", "scripts/tool.py"})


class TestCheckSkill(unittest.TestCase):
    def test_undeclared_file_on_disk_fails(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(Path(td), "undeclared", files={"orphan.md": "x"})
            errors = lint.check_skill(skill_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("orphan.md", errors[0])
            self.assertIn("not listed", errors[0])

    def test_stale_reference_in_frontmatter_fails(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(
                Path(td), "stale-ref",
                frontmatter_extra="files: ghost.md\n",
            )
            errors = lint.check_skill(skill_dir)
            self.assertEqual(len(errors), 1)
            self.assertIn("ghost.md", errors[0])
            self.assertIn("does not exist", errors[0])

    def test_fully_declared_skill_passes(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(
                Path(td), "clean",
                frontmatter_extra="files: a.md, scripts/b.py\n",
                files={"a.md": "x", "scripts/b.py": "y"},
            )
            self.assertEqual(lint.check_skill(skill_dir), [])

    def test_skill_with_no_sibling_files_and_no_files_field_passes(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill(Path(td), "solo")
            self.assertEqual(lint.check_skill(skill_dir), [])

    def test_missing_skill_md_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            not_a_skill = Path(td) / "archive"
            not_a_skill.mkdir()
            self.assertEqual(lint.check_skill(not_a_skill), [])


if __name__ == "__main__":
    unittest.main()
