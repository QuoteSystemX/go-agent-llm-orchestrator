#!/usr/bin/env python3
"""
skill_versioning.py — Manage version fields and lockfile for .agent/skills/

Usage:
    # Add version: 1.0.0 + Changelog to skills that are missing them, regenerate lockfile
    python3 .agent/scripts/skill_versioning.py

    # Preview what would change (no writes)
    python3 .agent/scripts/skill_versioning.py --dry-run

    # Bump version of a specific skill
    python3 .agent/scripts/skill_versioning.py --bump go-patterns --to 2.0.0

    # Only regenerate lockfile from current frontmatter
    python3 .agent/scripts/skill_versioning.py --lock-only
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent.parent
SKILLS_SRC = REPO_ROOT / ".agent" / "skills"
LOCK_FILE  = REPO_ROOT / ".agent" / "skill.lock"

DEFAULT_VERSION   = "1.0.0"
EMBED_END_MARKER  = "<!-- EMBED_END -->"
CHANGELOG_MARKER  = "## Changelog"

TODAY = datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# Frontmatter helpers (simple key: value parser — no PyYAML dependency)
# ---------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). frontmatter_block includes the --- delimiters."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[: end + 4], text[end + 4:].lstrip("\n")


def get_fm_value(fm_block: str, key: str) -> str:
    for line in fm_block.splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    return ""


def set_fm_value(fm_block: str, key: str, value: str) -> str:
    """Insert or replace a key in the frontmatter block (preserves all other keys)."""
    lines = fm_block.splitlines()
    new_line = f"{key}: {value}"
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            lines[i] = new_line
            return "\n".join(lines)
    # Insert before closing ---
    close = next((i for i, l in enumerate(lines) if l.strip() == "---" and i > 0), len(lines))
    lines.insert(close, new_line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def process_skill(skill_path: Path, dry_run: bool = False, force_version: str = "") -> dict:
    """
    Ensure skill has version in frontmatter and a ## Changelog section.
    Returns a dict with: name, version, changed (bool).
    """
    text = skill_path.read_text(encoding="utf-8")
    fm_block, body = split_frontmatter(text)

    name = skill_path.parent.name
    current_version = get_fm_value(fm_block, "version")
    changed = False

    # 1. Add version to frontmatter if missing
    if not current_version:
        new_version = force_version or DEFAULT_VERSION
        fm_block = set_fm_value(fm_block, "version", new_version)
        current_version = new_version
        changed = True
        print(f"  + version: {new_version} → {skill_path.relative_to(REPO_ROOT)}")
    elif force_version and force_version != current_version:
        fm_block = set_fm_value(fm_block, "version", force_version)
        old_version = current_version
        current_version = force_version
        changed = True
        print(f"  ↑ version: {old_version} → {force_version}  ({skill_path.relative_to(REPO_ROOT)})")

    # 2. Add ## Changelog section if missing
    if CHANGELOG_MARKER not in body:
        changelog_entry = (
            f"\n\n{CHANGELOG_MARKER}\n\n"
            f"- **{current_version}** ({TODAY}): Initial version\n"
        )
        if EMBED_END_MARKER in body:
            body = body.replace(EMBED_END_MARKER, changelog_entry + EMBED_END_MARKER)
        else:
            body = body.rstrip() + changelog_entry
        changed = True
        print(f"  + Changelog added → {skill_path.relative_to(REPO_ROOT)}")

    if changed and not dry_run:
        # Reconstruct: frontmatter + \n + body
        new_text = fm_block.rstrip() + "\n\n" + body.lstrip()
        skill_path.write_text(new_text, encoding="utf-8")

    return {"name": name, "version": current_version, "changed": changed}


def collect_top_level_skills() -> list[Path]:
    """Return SKILL.md files at depth=1 only (not game-development/2d-games/SKILL.md)."""
    return sorted(
        p for p in SKILLS_SRC.glob("*/SKILL.md")
        if p.parent.parent == SKILLS_SRC  # exactly one directory deep
    )


def generate_lockfile(skill_versions: dict[str, str], dry_run: bool = False) -> None:
    """Write .agent/skill.lock in simple YAML-like format."""
    lines = [
        "# .agent/skill.lock",
        "# Auto-generated — commit this file to freeze embedded skill versions.",
        "# To update: python3 .agent/scripts/skill_versioning.py",
        f"# Generated: {TODAY}",
        "version: 1",
        "skills:",
    ]
    for name in sorted(skill_versions):
        lines.append(f"  {name}: {skill_versions[name]}")

    content = "\n".join(lines) + "\n"

    if dry_run:
        print(f"\n[DRY] Would write {LOCK_FILE.relative_to(REPO_ROOT)}")
        print(content)
    else:
        LOCK_FILE.write_text(content, encoding="utf-8")
        print(f"\n✓ Lockfile written: {LOCK_FILE.relative_to(REPO_ROOT)} ({len(skill_versions)} skills)")


def load_lockfile() -> dict[str, str]:
    """Parse .agent/skill.lock → {skill_name: version}."""
    if not LOCK_FILE.exists():
        return {}
    result = {}
    for line in LOCK_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("version:") or line.startswith("generated:") or line == "skills:":
            continue
        m = re.match(r"^(\S+):\s+(\S+)$", line)
        if m:
            result[m.group(1)] = m.group(2)
    return result


def verify_against_lockfile(skill_versions: dict[str, str]) -> bool:
    """Returns True if all skill versions match lockfile. Prints warnings for mismatches."""
    locked = load_lockfile()
    if not locked:
        print("  [warn] No lockfile found — run without --verify to generate it.")
        return True

    ok = True
    for name, version in skill_versions.items():
        locked_ver = locked.get(name)
        if locked_ver and locked_ver != version:
            print(f"  [MISMATCH] {name}: lockfile={locked_ver}, current={version}")
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Manage skill versions and lockfile")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--lock-only", action="store_true", help="Only regenerate lockfile, skip SKILL.md edits")
    parser.add_argument("--bump", metavar="SKILL", help="Bump a specific skill to --to version")
    parser.add_argument("--to", metavar="VERSION", help="Target version for --bump")
    parser.add_argument("--verify", action="store_true", help="Verify skill versions match lockfile")
    args = parser.parse_args()

    if args.bump and not args.to:
        print("ERROR: --bump requires --to VERSION")
        sys.exit(1)

    skill_files = collect_top_level_skills()
    print(f"Found {len(skill_files)} top-level skills in {SKILLS_SRC.relative_to(REPO_ROOT)}\n")

    skill_versions: dict[str, str] = {}

    if not args.lock_only:
        print("=== Processing SKILL.md files ===")
        for path in skill_files:
            name = path.parent.name
            force_ver = args.to if (args.bump and name == args.bump) else ""
            result = process_skill(path, dry_run=args.dry_run, force_version=force_ver)
            skill_versions[result["name"]] = result["version"]
        if not any(process_skill(p, dry_run=True)["changed"] for p in skill_files):
            pass  # already printed per file
    else:
        # Just read current versions without modifying files
        for path in skill_files:
            text = path.read_text(encoding="utf-8")
            fm_block, _ = split_frontmatter(text)
            version = get_fm_value(fm_block, "version") or DEFAULT_VERSION
            skill_versions[path.parent.name] = version

    if args.verify:
        print("\n=== Verifying against lockfile ===")
        ok = verify_against_lockfile(skill_versions)
        sys.exit(0 if ok else 1)

    if not args.dry_run:
        generate_lockfile(skill_versions, dry_run=False)
    else:
        generate_lockfile(skill_versions, dry_run=True)


if __name__ == "__main__":
    main()
