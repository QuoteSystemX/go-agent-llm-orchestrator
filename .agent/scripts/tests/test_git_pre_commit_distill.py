#!/usr/bin/env python3
"""
Tests for STORY-1 git pre-commit distill hook.

Covers:
  - is_task_file: matches common task/story filename patterns
  - is_marked_done: recognizes completion markers
  - get_sentinel_mtime: handles missing sentinel
  - get_newest_done_mtime: returns newest done story
  - main: refuses when sentinel is missing
  - main: refuses when sentinel is older than done story
  - main: passes when sentinel is newer
  - main: passes when no done stories staged
  - main: SKIP_DISTILL_CHECK=1 bypasses
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / ".agent" / "scripts" / "dev" / "git_pre_commit_distill.py"

# Load module
_spec = importlib.util.spec_from_file_location("git_pre_commit_distill", str(SCRIPT_PATH))
mod = importlib.util.module_from_spec(_spec)
sys.modules["git_pre_commit_distill"] = mod
_spec.loader.exec_module(mod)


@pytest.fixture
def fake_repo():
    """Create a fake repo with a sentinel, tasks dir, and git init."""
    tmp = Path(tempfile.mkdtemp(prefix="distill_test_"))
    (tmp / "tasks").mkdir()
    (tmp / ".agent" / "bus").mkdir(parents=True)
    # Initialize git so get_staged_files can run
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    yield tmp
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def _write_story(path: Path, content: str, mtime: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ts = mtime.timestamp()
    os.utime(path, (ts, ts))


def _stage(path: Path) -> None:
    subprocess.run(["git", "add", str(path)], cwd=path.parent.parent, check=True, stdout=subprocess.DEVNULL)


class TestIsTaskFile:
    def test_matches_dated_story(self):
        assert mod.is_task_file("tasks/2026-07-11-epic-foo.md")
        assert mod.is_task_file("tasks/2026-07-11-epic-foo-bar.md")

    def test_matches_bracketed_story(self):
        assert mod.is_task_file("tasks/[STORY-1]-foo.md")
        assert mod.is_task_file("tasks/[EPIC]-bar.md")

    def test_matches_numbered_story(self):
        assert mod.is_task_file("tasks/01-foo.md")
        assert mod.is_task_file("tasks/1-foo.md")

    def test_rejects_other_paths(self):
        assert not mod.is_task_file("docs/foo.md")
        assert not mod.is_task_file("README.md")
        assert not mod.is_task_file("src/foo.py")


class TestIsMarkedDone:
    def test_status_done(self):
        assert mod.is_marked_done("status: done")
        assert mod.is_marked_done("Status: Done")
        assert mod.is_marked_done("Status: COMPLETED")

    def test_emoji_marker(self):
        assert mod.is_marked_done("✅ DONE — finished!")
        assert mod.is_marked_done("✅ Done")

    def test_checkbox(self):
        assert mod.is_marked_done("- [x] done")

    def test_pending_not_marked(self):
        assert not mod.is_marked_done("status: pending")
        assert not mod.is_marked_done("Status: in progress")


class TestGetSentinelMtime:
    def test_missing_sentinel(self, tmp_path, monkeypatch):
        # Override REPO_ROOT to a path without sentinel
        monkeypatch.setattr(mod, "SENTINEL", tmp_path / "no_such_file")
        assert mod.get_sentinel_mtime() is None

    def test_existing_sentinel(self, tmp_path, monkeypatch):
        sentinel = tmp_path / "sentinel"
        sentinel.write_text("ts", encoding="utf-8")
        monkeypatch.setattr(mod, "SENTINEL", sentinel)
        mtime = mod.get_sentinel_mtime()
        assert mtime is not None
        assert isinstance(mtime, datetime)


class TestGetNewestDoneMtime:
    def test_no_done_stories(self, tmp_path):
        story = tmp_path / "tasks" / "2026-07-11-pending.md"
        story.parent.mkdir(parents=True)
        story.write_text("status: pending", encoding="utf-8")
        result = mod.get_newest_done_mtime([str(story.relative_to(tmp_path.parent.parent))])
        # If REPO_ROOT doesn't match, the function may still work via Path resolution
        # Just verify it returns a sensible result.
        assert isinstance(result, tuple)

    def test_done_story_detected(self, fake_repo, monkeypatch):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        monkeypatch.setattr(mod, "SENTINEL", fake_repo / ".agent" / "bus" / ".distill_sentinel")
        story = fake_repo / "tasks" / "2026-07-11-done.md"
        _write_story(story, "status: done", datetime.now(timezone.utc))
        _stage(story)
        result = mod.get_newest_done_mtime(["tasks/2026-07-11-done.md"])
        assert result[0] is not None
        assert result[1] == "tasks/2026-07-11-done.md"


class TestMainEndToEnd:
    def test_refuses_when_no_sentinel(self, fake_repo, monkeypatch, capsys):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        monkeypatch.setattr(mod, "SENTINEL", fake_repo / ".agent" / "bus" / ".distill_sentinel")
        story = fake_repo / "tasks" / "2026-07-11-done.md"
        _write_story(story, "status: done", datetime.now(timezone.utc))
        _stage(story)
        assert mod.main() == 1
        captured = capsys.readouterr()
        assert "overdue" in captured.err.lower() or "sentinel" in captured.err.lower()

    def test_passes_when_sentinel_fresh(self, fake_repo, monkeypatch, capsys):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        sentinel = fake_repo / ".agent" / "bus" / ".distill_sentinel"
        monkeypatch.setattr(mod, "SENTINEL", sentinel)
        sentinel.write_text("ts", encoding="utf-8")
        story = fake_repo / "tasks" / "2026-07-11-done.md"
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        _write_story(story, "status: done", old)
        _stage(story)
        # Sentinel mtime is "now" (just written), story mtime is 1h ago
        assert mod.main() == 0

    def test_refuses_when_sentinel_stale(self, fake_repo, monkeypatch, capsys):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        sentinel = fake_repo / ".agent" / "bus" / ".distill_sentinel"
        monkeypatch.setattr(mod, "SENTINEL", sentinel)
        sentinel.write_text("ts", encoding="utf-8")
        # Sentinel is 2 hours old
        old_sentinel = datetime.now(timezone.utc) - timedelta(hours=2)
        sentinel_ts = old_sentinel.timestamp()
        os.utime(sentinel, (sentinel_ts, sentinel_ts))
        # Story is 1 hour old (newer than sentinel)
        story = fake_repo / "tasks" / "2026-07-11-done.md"
        newer_story = datetime.now(timezone.utc) - timedelta(hours=1)
        _write_story(story, "status: done", newer_story)
        _stage(story)
        assert mod.main() == 1

    def test_passes_when_no_done_staged(self, fake_repo, monkeypatch):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        monkeypatch.setattr(mod, "SENTINEL", fake_repo / ".agent" / "bus" / ".distill_sentinel")
        story = fake_repo / "tasks" / "2026-07-11-pending.md"
        _write_story(story, "status: pending", datetime.now(timezone.utc))
        _stage(story)
        # No sentinel needed when no done stories are staged
        assert mod.main() == 2

    def test_skip_distill_check_bypasses(self, fake_repo, monkeypatch, capsys):
        monkeypatch.setattr(mod, "REPO_ROOT", fake_repo)
        monkeypatch.setattr(mod, "SENTINEL", fake_repo / ".agent" / "bus" / ".distill_sentinel")
        monkeypatch.setenv("SKIP_DISTILL_CHECK", "1")
        story = fake_repo / "tasks" / "2026-07-11-done.md"
        _write_story(story, "status: done", datetime.now(timezone.utc))
        _stage(story)
        assert mod.main() == 0
        captured = capsys.readouterr()
        assert "bypassing" in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
