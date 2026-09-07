#!/usr/bin/env python3
import unittest
import shutil
import subprocess
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

import delivery.task_archive as archive


class TestTaskArchive(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_task_archive").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.test_root, check=True)
        self.done_dir = self.test_root / "tasks" / "done"
        self.done_dir.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def _git_add_all(self):
        subprocess.run(["git", "add", "-A"], cwd=self.test_root, check=True)

    def _git_add(self, *rel_paths: str):
        subprocess.run(["git", "add", *rel_paths], cwd=self.test_root, check=True)

    def _write(self, rel_path: str, content: str) -> Path:
        p = self.test_root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    # -- rewrite_links -------------------------------------------------------

    def test_partition_rewrites_references_elsewhere(self):
        self._write("tasks/done/2026-08-12-foo.md", "# Foo\n")
        ref = self._write("server/handler.go", "// see tasks/done/2026-08-12-foo.md for context\n")
        self._git_add_all()

        archive.partition(self.done_dir, dry_run=False, root=self.test_root)
        changed, dangling = archive.rewrite_links(self.test_root, self.done_dir, dry_run=False)

        self.assertEqual(dangling, [])
        self.assertIn(ref, changed)
        self.assertEqual(
            ref.read_text(encoding="utf-8"),
            "// see tasks/done/2026-08/2026-08-12-foo.md for context\n",
        )

    def test_rewrite_is_idempotent(self):
        self._write("tasks/done/2026-08/2026-08-12-foo.md", "# Foo\n")
        ref = self._write("server/handler.go", "// see tasks/done/2026-08-12-foo.md\n")
        self._git_add_all()

        changed1, _ = archive.rewrite_links(self.test_root, self.done_dir, dry_run=False)
        self.assertIn(ref, changed1)
        rewritten = ref.read_text(encoding="utf-8")

        changed2, dangling2 = archive.rewrite_links(self.test_root, self.done_dir, dry_run=False)
        self.assertEqual(changed2, {})
        self.assertEqual(dangling2, [])
        self.assertEqual(ref.read_text(encoding="utf-8"), rewritten)

    def test_untracked_and_gitignored_files_untouched(self):
        self._write("tasks/done/2026-08/2026-08-12-foo.md", "# Foo\n")
        self._write(".gitignore", "server/ignored.go\n")
        self._git_add_all()  # baseline: done card + .gitignore staged

        # Neither is ever staged, so neither ever enters `git ls-files`: unstaged.go simply
        # because we don't call `git add` again, ignored.go because .gitignore excludes it even
        # if we did.
        unstaged = self._write("server/unstaged.go", "// see tasks/done/2026-08-12-foo.md\n")
        ignored = self._write("server/ignored.go", "// see tasks/done/2026-08-12-foo.md\n")

        changed, _ = archive.rewrite_links(self.test_root, self.done_dir, dry_run=False)

        self.assertNotIn(unstaged, changed)
        self.assertNotIn(ignored, changed)
        self.assertIn("tasks/done/2026-08-12-foo.md", unstaged.read_text(encoding="utf-8"))
        self.assertIn("tasks/done/2026-08-12-foo.md", ignored.read_text(encoding="utf-8"))

    def test_dangling_reference_reported_not_rewritten(self):
        ref = self._write("server/handler.go", "// see tasks/done/2026-08-12-nonexistent.md\n")
        self._git_add_all()

        changed, dangling = archive.rewrite_links(self.test_root, self.done_dir, dry_run=False)

        self.assertEqual(changed, {})
        self.assertEqual(len(dangling), 1)
        self.assertEqual(dangling[0], (ref, "done/2026-08-12-nonexistent.md"))
        self.assertIn("2026-08-12-nonexistent.md", ref.read_text(encoding="utf-8"))

    # -- main() / --check -----------------------------------------------------

    def _run_main(self, *extra_args) -> int:
        argv = ["task_archive.py", "--root", str(self.test_root), *extra_args]
        with patch.object(sys, "argv", argv):
            try:
                archive.main()
            except SystemExit as e:
                return e.code or 0
        return 0

    def test_partition_and_index_basic_flow(self):
        self._write("tasks/done/2026-08-12-foo.md", "# Foo\n")
        self._git_add_all()

        code = self._run_main()

        self.assertEqual(code, 0)
        self.assertTrue((self.done_dir / "2026-08" / "2026-08-12-foo.md").exists())
        self.assertTrue((self.done_dir / "INDEX.md").exists())
        self.assertIn("2026-08-12", (self.done_dir / "INDEX.md").read_text(encoding="utf-8"))

    def test_partition_uses_git_mv_for_tracked_cards(self):
        # Found in review: is_tracked()/partition() used to hard-code cwd=REPO_ROOT (the real
        # checkout) regardless of the `root` a caller passed, so a tracked card under a --root
        # override always looked untracked and silently fell back to a plain rename — losing git
        # history with no error. Assert the real `git mv` path fires: git detects a staged rename
        # (`R`), not a delete+add pair, for a card that was actually tracked before the move.
        # Rename detection needs a committed baseline to compare against — a file only ever
        # `git add`ed (never committed) has no HEAD-side history for `git status` to diff a move
        # against, so it would trivially show as a fresh "A" either way and not exercise this path.
        self._write("tasks/done/2026-08-12-foo.md", "# Foo\n")
        self._git_add_all()
        subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=self.test_root, check=True)

        archive.partition(self.done_dir, dry_run=False, root=self.test_root)

        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=self.test_root, capture_output=True, text=True,
        ).stdout
        self.assertIn("R  tasks/done/2026-08-12-foo.md -> tasks/done/2026-08/2026-08-12-foo.md", status)

    def test_check_fails_on_stale_links(self):
        self._write("tasks/done/2026-08-12-foo.md", "# Foo\n")
        self._git_add_all()
        self._run_main()  # partitions + rewrites INDEX, produces a clean baseline
        self._git_add_all()

        # Introduce fresh drift: a new tracked file with a flat reference the partitioned tree
        # already has an answer for.
        self._write("server/handler.go", "// see tasks/done/2026-08-12-foo.md\n")
        self._git_add_all()

        code = self._run_main("--check")
        self.assertEqual(code, 1)

    def test_check_passes_after_rewrite(self):
        self._write("tasks/done/2026-08-12-foo.md", "# Foo\n")
        self._write("server/handler.go", "// see tasks/done/2026-08-12-foo.md\n")
        self._git_add_all()

        self._run_main()  # partitions, rewrites INDEX and the stale reference
        self._git_add_all()

        code = self._run_main("--check")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
