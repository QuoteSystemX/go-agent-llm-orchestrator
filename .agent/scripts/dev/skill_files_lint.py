#!/usr/bin/env python3
"""
Skill files: frontmatter drift check.

Every skill under .agent/skills/<name>/ may declare a `files:` field in its
SKILL.md YAML frontmatter — a comma-separated list of sibling file paths
(relative to the skill directory) that ship with the skill. This is the
SOLE mechanism for deciding which sibling files a skill carries when
imported (e.g. via Multica's MCP skill import) — there is no directory-walk
/ auto-discover fallback, by design. See
multica repo tasks/2026-08-13-mcp-skill-import-drops-sibling-files.md for
the full design decision and why auto-discovery was rejected.

Because files: is hand-maintained, it can drift from what's actually on
disk in two directions:
  (a) a file exists in the skill directory but isn't listed in files: —
      it will silently NOT ship with the skill.
  (b) files: references a path that doesn't exist on disk — a stale
      reference (the same class of bug as
      tasks/done/2026-08-11-bug-skill-broken-link-adr-template-architecture-efe79c.md).

This script catches both directions and fails loudly instead of letting
either drift silently, without ever changing what gets imported at runtime.

Usage:
  python3 .agent/scripts/dev/skill_files_lint.py
  python3 .agent/scripts/dev/skill_files_lint.py --skill architecture

Exit codes:
  0  all skills' files: lists match disk
  1  at least one skill has drift (see stderr for details)
  2  no skills directory found
"""
import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / ".agent" / "skills"

FRONTMATTER_RE = re.compile(r"(?s)^---\s*\n(.*?)\n---")

# Same junk patterns CLAUDE.md already codifies as forbidden-in-PR (see the
# "FORBIDDEN FILES IN ANY PR" table) — a skill directory that happens to
# contain one of these should never require a files: entry for it, and the
# retrofit script (skill_files_retrofit.py) must never propose adding one.
JUNK_PATTERNS = [
    "*.orig", "*.bak", "*.tmp", "*.swp", "*.swo", "*.diff", "*.patch", "*~",
    "*.log", ".DS_Store", "Thumbs.db", "*.pyc",
]
JUNK_DIR_NAMES = {"__pycache__"}


def parse_files_field(skill_md_text: str) -> str | None:
    """Extract the raw `files:` frontmatter value, or None if absent.

    Matches the single-line comma-separated convention already used by
    `allowed-tools:` in these SKILL.md files (see
    parseMcpFilesList/parseMcpFrontmatter in multica's server/internal/handler/mcp.go)
    — not a multi-line YAML list.
    """
    m = FRONTMATTER_RE.match(skill_md_text)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        if key.strip() == "files":
            return val.strip()
    return None


def declared_paths(files_field: str | None) -> list[str]:
    if not files_field:
        return []
    return [p.strip() for p in files_field.split(",") if p.strip()]


def is_junk(rel_path: Path) -> bool:
    if rel_path.name == "SKILL.md":
        return True
    if any(part in JUNK_DIR_NAMES for part in rel_path.parts):
        return True
    return any(rel_path.match(pat) for pat in JUNK_PATTERNS)


def disk_files(skill_dir: Path) -> set[str]:
    """All non-junk file paths under skill_dir, relative, POSIX-separated."""
    found = set()
    for p in skill_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(skill_dir)
        if is_junk(rel):
            continue
        found.add(rel.as_posix())
    return found


def check_skill(skill_dir: Path) -> list[str]:
    """Return a list of human-readable drift errors for one skill (empty = clean)."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        # Not a skill directory (e.g. .agent/skills/archive/ is a container
        # for retired skill subdirectories, not a skill itself) — nothing to
        # check. main() already filters these out before calling here; this
        # branch is just a defensive fallback.
        return []

    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"{skill_dir.name}: failed to read SKILL.md: {e}"]

    declared = set(declared_paths(parse_files_field(text)))
    on_disk = disk_files(skill_dir)

    errors = []
    for undeclared in sorted(on_disk - declared):
        errors.append(
            f"{skill_dir.name}: {undeclared!r} exists on disk but is not listed in "
            f"SKILL.md's files: frontmatter — it will not ship with this skill"
        )
    for missing in sorted(declared - on_disk):
        errors.append(
            f"{skill_dir.name}: files: references {missing!r} but that path does not "
            f"exist on disk — stale/broken reference"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", help="Only check this one skill (directory name).")
    args = parser.parse_args()

    if not SKILLS_DIR.exists():
        print(f"[skill-files-lint] no skills directory found at {SKILLS_DIR}", file=sys.stderr)
        return 2

    skill_dirs = sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").exists()
    )
    if args.skill:
        skill_dirs = [d for d in skill_dirs if d.name == args.skill]
        if not skill_dirs:
            print(f"[skill-files-lint] no such skill: {args.skill}", file=sys.stderr)
            return 2

    all_errors: list[str] = []
    for skill_dir in skill_dirs:
        all_errors.extend(check_skill(skill_dir))

    if all_errors:
        print(f"[skill-files-lint] {len(all_errors)} drift issue(s) found:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\n  Fix: update the offending skill's SKILL.md files: frontmatter to match "
            "disk, or run skill_files_retrofit.py --skill <name> to reseed it.",
            file=sys.stderr,
        )
        return 1

    print(f"[skill-files-lint] OK — {len(skill_dirs)} skill(s) checked, files: matches disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
