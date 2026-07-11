#!/usr/bin/env python3
"""
STORY-1 Forcing Function: git pre-commit distillation check.

Refuses to commit a story card marked as 'done' unless the distillation
pipeline (archivist_trigger.py) has been run since the card was last edited.

Behavior:
  - Scans staged task/story files (tasks/[STORY]-*.md, tasks/[0-9]*.md)
  - For each file with status indicating completion (e.g., "✅ DONE", "[x]",
    "Status: completed", "Status: done"), verify distillation freshness.
  - Distillation freshness is tracked via a sentinel file:
      .agent/bus/.distill_sentinel
    which archivist_trigger.py writes on every successful run.
  - If the sentinel is older than the most recently modified done-story,
    the commit is refused with a clear remediation message.

Exit codes:
  0  all clear (commit proceeds)
  1  distill overdue (commit refused; prints remediation)
  2  no staged files of interest (commit proceeds)

This script is intended to be invoked by the pre-commit hook installed via
`make install-hooks`. It is independent of pre_commit_review.py (which
checks lessons) — both should run on commit.

Override:
  SKIP_DISTILL_CHECK=1   bypass the check (e.g., for emergency hotfix commits)
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SENTINEL = REPO_ROOT / ".agent" / "bus" / ".distill_sentinel"
TASKS_DIR = REPO_ROOT / "tasks"
DONE_DIR = REPO_ROOT / "tasks" / "done"

# Patterns that mark a story as completed
DONE_PATTERNS = [
    re.compile(r"^status:\s*done", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^status:\s*completed", re.IGNORECASE | re.MULTILINE),
    re.compile(r"✅\s*DONE", re.IGNORECASE),
    re.compile(r"\[x\]\s*done", re.IGNORECASE),
]


def get_staged_files() -> list[str]:
    """Return list of staged file paths (relative to REPO_ROOT)."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
    except Exception:
        return []
    return [line for line in out.splitlines() if line]


def is_task_file(path: str) -> bool:
    """Heuristic: looks like a story/task card."""
    if not (path.startswith("tasks/") or path.startswith("./tasks/")):
        return False
    name = Path(path).name
    # Match patterns: 2026-07-11-epic-...md, [STORY]-...md, 01-...md, etc.
    if re.match(r"^\d{4}-\d{2}-\d{2}-.*\.md$", name):
        return True
    if re.match(r"^\[.+\]-.*\.md$", name):
        return True
    if re.match(r"^\d+[-_].*\.md$", name):
        return True
    return False


def is_marked_done(content: str) -> bool:
    for pat in DONE_PATTERNS:
        if pat.search(content):
            return True
    return False


def get_sentinel_mtime() -> datetime | None:
    if not SENTINEL.exists():
        return None
    ts = SENTINEL.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def get_newest_done_mtime(staged_files: list[str]) -> tuple[datetime | None, str | None]:
    """Return the mtime of the newest staged file marked as done, with path."""
    newest: tuple[datetime | None, str | None] = (None, None)
    for rel in staged_files:
        full = REPO_ROOT / rel
        if not full.exists() or not full.is_file():
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not is_marked_done(content):
            continue
        mtime = datetime.fromtimestamp(full.stat().st_mtime, tz=timezone.utc)
        if newest[0] is None or mtime > newest[0]:
            newest = (mtime, rel)
    return newest


def main() -> int:
    if os.environ.get("SKIP_DISTILL_CHECK") == "1":
        print("ℹ️  SKIP_DISTILL_CHECK=1 — bypassing distill check")
        return 0

    staged = get_staged_files()
    task_files = [f for f in staged if is_task_file(f)]
    if not task_files:
        return 2  # no relevant staged files

    newest_mtime, newest_path = get_newest_done_mtime(task_files)
    if newest_mtime is None:
        return 2  # no done stories staged

    sentinel_mtime = get_sentinel_mtime()
    if sentinel_mtime is None:
        print("❌ Distill overdue: no .agent/bus/.distill_sentinel found.", file=sys.stderr)
        print(f"   Staged done-story: {newest_path}", file=sys.stderr)
        print("   Fix: run `python3 .agent/scripts/knowledge/archivist_trigger.py`", file=sys.stderr)
        print("   Or: `SKIP_DISTILL_CHECK=1 git commit ...` (emergency only)", file=sys.stderr)
        return 1

    if sentinel_mtime < newest_mtime:
        age = (newest_mtime - sentinel_mtime).total_seconds()
        print("❌ Distill overdue: story marked done AFTER last distill run.", file=sys.stderr)
        print(f"   Staged done-story: {newest_path}", file=sys.stderr)
        print(f"   Story mtime:  {newest_mtime.isoformat()}", file=sys.stderr)
        print(f"   Sentinel mtime: {sentinel_mtime.isoformat()}", file=sys.stderr)
        print(f"   Drift: {age:.0f}s", file=sys.stderr)
        print("   Fix: run `python3 .agent/scripts/knowledge/archivist_trigger.py`", file=sys.stderr)
        print("   Or:  `SKIP_DISTILL_CHECK=1 git commit ...` (emergency only)", file=sys.stderr)
        return 1

    print(f"✅ Distill fresh (sentinel at {sentinel_mtime.isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
