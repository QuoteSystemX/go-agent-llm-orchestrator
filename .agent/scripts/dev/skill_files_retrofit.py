#!/usr/bin/env python3
"""
One-time retrofit: seed SKILL.md `files:` frontmatter from current disk state.

skill_files_lint.py (same directory) enforces that every skill's files:
frontmatter matches what's actually on disk — but on day one, none of the
existing skills under .agent/skills/ have a files: field at all, so the
lint check would fail every skill that happens to have sibling files with
no baseline to diff against. This script seeds that baseline once: for
each skill directory, list its non-junk sibling files (same exclusion
rules as skill_files_lint.py, reused directly — not duplicated) and write
them into a new `files:` line in SKILL.md's frontmatter.

By default this SKIPS any skill that already has a non-empty files: field —
it never overwrites a hand-curated list. Pass --force to reseed those too
(useful only for verifying the tool itself; not needed for the initial
retrofit since nothing has files: yet).

Usage:
  python3 .agent/scripts/dev/skill_files_retrofit.py --dry-run   # preview
  python3 .agent/scripts/dev/skill_files_retrofit.py             # write
  python3 .agent/scripts/dev/skill_files_retrofit.py --skill architecture

Exit codes:
  0  ran successfully (whether or not any skill needed seeding)
  2  no skills directory found
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_files_lint import (  # noqa: E402
    REPO_ROOT,
    SKILLS_DIR,
    FRONTMATTER_RE,
    declared_paths,
    disk_files,
    parse_files_field,
)


def render_files_line(paths: set[str]) -> str:
    return "files: " + ", ".join(sorted(paths))


def upsert_files_line(skill_md_text: str, files_line: str) -> str:
    """Insert or replace the files: line inside the frontmatter block,
    leaving every other line untouched."""
    m = FRONTMATTER_RE.match(skill_md_text)
    if not m:
        raise ValueError("no frontmatter block found")

    body = m.group(1)
    lines = body.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if ":" in line and line.split(":", 1)[0].strip() == "files":
            lines[i] = files_line
            replaced = True
            break
    if not replaced:
        lines.append(files_line)

    new_body = "\n".join(lines)
    return skill_md_text[: m.start(1)] + new_body + skill_md_text[m.end(1) :]


def process_skill(skill_dir: Path, force: bool, dry_run: bool) -> str:
    """Returns one of: 'seeded', 'skipped-no-files', 'skipped-already-set', 'error:...'"""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        # main() already filters these out; defensive fallback only.
        return "skipped-not-a-skill"

    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"error: read failed: {e}"

    existing = declared_paths(parse_files_field(text))
    if existing and not force:
        return "skipped-already-set"

    on_disk = disk_files(skill_dir)
    if not on_disk:
        return "skipped-no-files"

    files_line = render_files_line(on_disk)
    try:
        new_text = upsert_files_line(text, files_line)
    except ValueError as e:
        return f"error: {e}"

    if not dry_run:
        skill_md.write_text(new_text, encoding="utf-8")
    return "seeded"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", help="Only retrofit this one skill (directory name).")
    parser.add_argument("--force", action="store_true", help="Reseed even if files: is already set.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change, write nothing.")
    args = parser.parse_args()

    if not SKILLS_DIR.exists():
        print(f"[skill-files-retrofit] no skills directory found at {SKILLS_DIR}", file=sys.stderr)
        return 2

    skill_dirs = sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").exists()
    )
    if args.skill:
        skill_dirs = [d for d in skill_dirs if d.name == args.skill]
        if not skill_dirs:
            print(f"[skill-files-retrofit] no such skill: {args.skill}", file=sys.stderr)
            return 2

    counts = {
        "seeded": 0, "skipped-no-files": 0, "skipped-already-set": 0,
        "skipped-not-a-skill": 0, "error": 0,
    }
    for skill_dir in skill_dirs:
        result = process_skill(skill_dir, force=args.force, dry_run=args.dry_run)
        if result.startswith("error"):
            counts["error"] += 1
            print(f"  ! {skill_dir.name}: {result}", file=sys.stderr)
        elif result == "seeded":
            counts["seeded"] += 1
            verb = "would seed" if args.dry_run else "seeded"
            print(f"  + {skill_dir.name}: {verb} files:")
        else:
            counts[result] += 1

    mode = "DRY RUN — " if args.dry_run else ""
    print(
        f"[skill-files-retrofit] {mode}{counts['seeded']} seeded, "
        f"{counts['skipped-no-files']} had no sibling files, "
        f"{counts['skipped-already-set']} already had files: set, "
        f"{counts['error']} errors (of {len(skill_dirs)} skills checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
