#!/usr/bin/env python3
"""
obsidian_validator.py — Obsidian Vault Validator & Migration Tool

Subcommands:
  check       Validate vault contents (links, frontmatter, callouts, orphans)
  status      Diagnose vault and repo documentation state
  init        Create a new Obsidian vault from scratch
  migrate     Convert existing wiki files to OFM compliance
  merge       Merge docs/ content into the vault

Usage:
  python3 obsidian_validator.py check [--fix] [--json] [--path <dir>]
  python3 obsidian_validator.py status [--json]
  python3 obsidian_validator.py init [--path <dir>]
  python3 obsidian_validator.py migrate [--dry-run] [--backup]
  python3 obsidian_validator.py merge --from <dir> [--dry-run]
"""

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_VAULT = "wiki"
REQUIRED_FRONTMATTER = ["title", "tags", "status"]
CALLOUT_TYPES = [
    "note", "tip", "warning", "info", "example", "quote",
    "bug", "danger", "success", "failure", "question",
    "abstract", "todo", "important", "check", "faq",
    "cite", "definition", "summary", "reference",
]
DOC_DIR_SIGNALS = ["docs", "documentation", "wiki", "guide", "manual"]
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".obsidian", ".gitbook", "obsidian_vault", "fragments"}


# ─── VaultDetector ───────────────────────────────────────────────────────────

class VaultDetector:
    """Scans repository for documentation and vault state."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def find_vault(self, path: Optional[str] = None) -> Optional[Path]:
        """Find the vault directory. Checks explicit path, then DEFAULT_VAULT."""
        if path:
            candidate = self.root / path
            if candidate.exists():
                return candidate
            return None
        candidate = self.root / DEFAULT_VAULT
        if candidate.exists():
            return candidate
        return None

    def find_doc_dirs(self) -> list[Path]:
        """Scan root for documentation directories (docs/, wiki/, guide/, etc.)."""
        found = []
        for entry in self.root.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name in IGNORE_DIRS:
                continue
            name_lower = entry.name.lower()
            if any(signal in name_lower for signal in DOC_DIR_SIGNALS):
                md_count = len(list(entry.rglob("*.md")))
                if md_count > 0:
                    found.append(entry)
        return found

    def count_md_files(self, directory: Path) -> int:
        """Count .md files in a directory recursively (excluding ignored dirs)."""
        count = 0
        for path in directory.rglob("*.md"):
            try:
                rel = path.relative_to(directory)
                if any(part in IGNORE_DIRS for part in rel.parts):
                    continue
                count += 1
            except ValueError:
                count += 1
        return count

    def has_other_doc_format(self, directory: Path) -> list[str]:
        """Detect non-.md documentation formats."""
        formats = []
        if list(directory.rglob("*.rst")):
            formats.append("RST")
        if list(directory.rglob("*.adoc")) or list(directory.rglob("*.asciidoc")):
            formats.append("AsciiDoc")
        if list(directory.rglob("*.tex")):
            formats.append("LaTeX")
        if list(directory.rglob("*.ipynb")):
            formats.append("Jupyter")
        return formats


# ─── Validator ───────────────────────────────────────────────────────────────

class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        self.broken_links: list[tuple[str, str]] = []
        self.orphans: set[str] = set()
        self.missing_frontmatter: list[tuple[str, list[str]]] = []
        self.invalid_callouts: list[tuple[str, str, int]] = []
        self.errors: int = 0
        self.warnings: int = 0

    @property
    def is_clean(self) -> bool:
        return (
            len(self.broken_links) == 0
            and len(self.orphans) == 0
            and len(self.missing_frontmatter) == 0
            and len(self.invalid_callouts) == 0
            and self.errors == 0
        )

    @property
    def compliance_pct(self) -> float:
        """Estimated OFM compliance percentage based on issues found.
        
        Weighting:
        - Broken links: -15% each (critical — breaks navigation)
        - Missing frontmatter: -5% each (important for graph)
        - Invalid callouts: -3% each (syntax issue)
        - Orphans: -1% each (normal for leaf files)
        - Errors: -10% each
        """
        score = 100.0
        score -= len(self.broken_links) * 15
        score -= len(self.missing_frontmatter) * 5
        score -= len(self.invalid_callouts) * 3
        score -= len(self.orphans) * 1
        score -= self.errors * 10
        return max(0.0, min(100.0, score))

    def to_dict(self) -> dict:
        return {
            "broken_links": [{"source": s, "target": t} for s, t in self.broken_links],
            "orphans": sorted(self.orphans),
            "missing_frontmatter": [
                {"file": f, "missing": m} for f, m in self.missing_frontmatter
            ],
            "invalid_callouts": [
                {"file": f, "content": c, "line": l} for f, c, l in self.invalid_callouts
            ],
            "errors": self.errors,
            "warnings": self.warnings,
            "compliance_pct": self.compliance_pct,
            "is_clean": self.is_clean,
        }


class Validator:
    """Validates vault contents for OFM compliance."""

    def __init__(self, vault_path: Path):
        self.vault = vault_path.resolve()

    def validate_all(self) -> ValidationResult:
        """Run all validation checks."""
        result = ValidationResult()
        self._check_links(result)
        self._check_frontmatter(result)
        self._check_callouts(result)
        return result

    def _get_all_md_files(self) -> list[Path]:
        """Get all .md files, excluding ignored directories."""
        result = []
        for path in self.vault.rglob("*.md"):
            # Skip files in ignored directories
            rel = path.relative_to(self.vault)
            if any(part in IGNORE_DIRS for part in rel.parts):
                continue
            result.append(path)
        return result

    def _get_file_names(self) -> set[str]:
        return {f.stem for f in self._get_all_md_files()}

    def _check_links(self, result: ValidationResult):
        """Check for broken wikilinks and orphan files."""
        all_files = self._get_all_md_files()
        file_names = self._get_file_names()

        # Build a lookup: resolved path basename → set of stems/paths
        # This handles both simple [[Note]] and path-based [[directory/Note]]
        file_stems = {f.stem for f in all_files}
        file_path_stems = set()
        for f in all_files:
            rel = f.relative_to(self.vault)
            # Get the relative path without extension (e.g., "decisions/_index")
            no_ext = str(rel.parent / rel.stem) if rel.suffix else str(rel)
            file_path_stems.add(no_ext)
            # Also add just the stem for simple lookups
            file_path_stems.add(rel.stem)

        orphans = set(file_stems)
        orphans.discard("index")
        orphans.discard("README")
        orphans.discard("ROADMAP")
        orphans.discard("_index")
        orphans.discard("INDEX")
        orphans.discard("GLOSSARY")
        orphans.discard("CONTRIBUTING")

        # Ignore templates and hidden stems
        for stem in list(orphans):
            if stem.startswith(".") or ".template" in stem or "TEMPLATE" in stem:
                orphans.discard(stem)

        for file_path in all_files:
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                result.errors += 1
                continue

            links = re.findall(r"\[\[(.*?)\]\]", content)
            for link in links:
                # Split by | for aliases, then # for sections
                target_raw = link.split("|")[0].split("#")[0].strip()
                # Clean trailing backslash from table-escaped pipes (\|)
                target_raw = target_raw.rstrip("\\")
                # Strip .md from target if present (some wikilinks include extension)
                target = re.sub(r'\.md$', '', target_raw)

                if not target:
                    continue

                # Check both: simple stem name AND path-based resolution
                target_exists = target in file_stems or target in file_path_stems
                if not target_exists:
                    result.broken_links.append((str(file_path.name), target_raw))
                if target in orphans:
                    orphans.remove(target)

        result.orphans = orphans

    def _check_frontmatter(self, result: ValidationResult):
        """Check for missing required frontmatter fields."""
        for file_path in self._get_all_md_files():
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            # Use relative path from vault root for consistent lookups
            rel_path = file_path.relative_to(self.vault)

            if not content.startswith("---"):
                result.missing_frontmatter.append((str(rel_path), REQUIRED_FRONTMATTER))
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                result.missing_frontmatter.append((str(rel_path), REQUIRED_FRONTMATTER))
                continue

            fm_text = parts[1]
            present = set()
            for line in fm_text.strip().splitlines():
                if ":" in line:
                    key = line.split(":", 1)[0].strip()
                    present.add(key)

            missing = [f for f in REQUIRED_FRONTMATTER if f not in present]
            if missing:
                result.missing_frontmatter.append((str(rel_path), missing))

    def _check_callouts(self, result: ValidationResult):
        """Check for callout syntax issues."""
        for file_path in self._get_all_md_files():
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("> [!"):
                    match = re.match(r">\s*\[!(\w+(?:-\w+)*)\]", stripped)
                    if match:
                        callout_type = match.group(1).lower()
                        if callout_type not in CALLOUT_TYPES:
                            result.warnings += 1
                    else:
                        result.invalid_callouts.append(
                            (file_path.name, stripped[:60], line_num)
                        )


# ─── Repairer ────────────────────────────────────────────────────────────────

class Repairer:
    """Auto-fix common vault issues."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault = vault_path.resolve()
        self.dry_run = dry_run
        self.fixes_applied = 0

    def fix_broken_links(self, result: ValidationResult) -> int:
        """Create stub files for broken wikilink targets."""
        fixed = 0
        for source, target in result.broken_links:
            # Strip .md from target if present (some wikilinks include extension)
            clean_target = re.sub(r'\.md$', '', target.strip())
            stub_path = self.vault / f"{clean_target}.md"
            if stub_path.exists():
                continue
            if self.dry_run:
                print(f"  🔧 Would create: {stub_path.name}")
                fixed += 1
                continue
            stub_path.write_text(
                f"# {target}\n\n"
                f"> [!note] Auto-generated stub\n"
                f"This file was created by `obsidian_validator.py --fix` to resolve a broken wikilink.\n"
                f"Referenced from: [[{source}]]\n"
            )
            fixed += 1
        self.fixes_applied += fixed
        return fixed

    def add_frontmatter(self, result: ValidationResult) -> int:
        """Add missing required frontmatter to files."""
        fixed = 0
        for file_name, missing in result.missing_frontmatter:
            file_path = self.vault / file_name
            if not file_path.exists():
                continue
            if self.dry_run:
                print(f"  🔧 Would add frontmatter to: {file_name}")
                fixed += 1
                continue

            content = file_path.read_text(encoding="utf-8")
            fm_lines = ["---"]
            if "title" in missing:
                title = file_path.stem.replace("-", " ").replace("_", " ").title()
                fm_lines.append(f'title: "{title}"')
            if "tags" in missing:
                fm_lines.append("tags:")
                fm_lines.append("  - project")
            if "status" in missing:
                fm_lines.append("status: proposed")
            fm_lines.append("---\n")

            if content.startswith("---"):
                # There's partial frontmatter, try to merge
                parts = content.split("---", 2)
                existing_fm = parts[1]
                new_fm = fm_lines[1:-1]  # skip the --- markers
                merged = "---\n" + existing_fm.rstrip() + "\n"
                for line in new_fm:
                    key = line.split(":")[0].strip()
                    if key not in existing_fm:
                        merged += line + "\n"
                merged += "---\n" + (parts[2] if len(parts) > 2 else "")
                file_path.write_text(merged)
            else:
                file_path.write_text("\n".join(fm_lines) + "\n" + content)

            fixed += 1
        self.fixes_applied += fixed
        return fixed


# ─── Migrator ────────────────────────────────────────────────────────────────

class Migrator:
    """Migrate existing docs into OFM-compliant vault."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault = vault_path.resolve()
        self.dry_run = dry_run

    def init_vault(self, create_obsidian_dir: bool = True) -> int:
        """Initialize an empty vault structure."""
        created = 0

        if not self.vault.exists():
            if self.dry_run:
                print(f"  🔧 Would create: {self.vault}/")
                created += 1
            else:
                self.vault.mkdir(parents=True)
                created += 1

        if create_obsidian_dir:
            obsidian_dir = self.vault / ".obsidian"
            if not obsidian_dir.exists():
                if self.dry_run:
                    print(f"  🔧 Would create: {obsidian_dir}/")
                    created += 1
                else:
                    obsidian_dir.mkdir(exist_ok=True)
                    (obsidian_dir / "app.json").write_text(
                        '{\n  "alwaysUpdateLinks": true,\n'
                        '  "showFrontmatter": true,\n'
                        '  "showLineNumber": true,\n'
                        '  "wikiLinks": true\n}\n'
                    )
                    created += 1

        # Create _index.md if missing
        index_file = self.vault / "_index.md"
        if not index_file.exists():
            if self.dry_run:
                print(f"  🔧 Would create: _index.md")
                created += 1
            else:
                index_file.write_text(
                    "---\ntitle: \"Vault Home\"\n"
                    "tags:\n  - project\nstatus: active\n---\n\n"
                    "# Vault Home\n\n"
                    "Welcome to the Obsidian vault. This is a Map of Content (MOC).\n\n"
                    "## Contents\n\n"
                    "- See [[ARCHITECTURE]] for system overview\n"
                )
                created += 1

        return created

    def merge_from(self, source: Path) -> int:
        """Merge documentation from another directory into vault."""
        moved = 0
        for item in source.rglob("*.md"):
            rel_path = item.relative_to(source)
            dest = self.vault / rel_path
            if dest.exists():
                continue
            if self.dry_run:
                print(f"  🔧 Would move: {rel_path}")
                moved += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            moved += 1
        return moved


# ─── Formatter ───────────────────────────────────────────────────────────────

class Formatter:
    """Format validation results for output."""

    @staticmethod
    def text_report(result: ValidationResult, vault_path: str):
        """Print human-readable report."""
        print(f"\n{'='*55}")
        print(f"  🏛️  VAULT HEALTH REPORT — {vault_path}")
        print(f"{'='*55}")

        print(f"\n📊 OFM Compliance: {result.compliance_pct:.0f}%")
        print(f"{'─'*55}")

        if result.broken_links:
            print(f"\n❌ Broken Links ({len(result.broken_links)}):")
            for source, target in result.broken_links[:10]:
                print(f"  • {source} → [[{target}]]")
            if len(result.broken_links) > 10:
                print(f"  ... and {len(result.broken_links) - 10} more")
        else:
            print(f"\n✅ No broken links.")

        if result.orphans:
            print(f"\n⚠️  Orphan Files ({len(result.orphans)}):")
            for orphan in sorted(result.orphans)[:10]:
                print(f"  • {orphan}.md")
            if len(result.orphans) > 10:
                print(f"  ... and {len(result.orphans) - 10} more")
        else:
            print(f"\n✅ No orphan files.")

        if result.missing_frontmatter:
            print(f"\n⚠️  Missing Frontmatter ({len(result.missing_frontmatter)}):")
            for file_name, missing in result.missing_frontmatter[:10]:
                print(f"  • {file_name}: missing {', '.join(missing)}")
            if len(result.missing_frontmatter) > 10:
                print(f"  ... and {len(result.missing_frontmatter) - 10} more")
        else:
            print(f"\n✅ All files have required frontmatter.")

        if result.invalid_callouts:
            print(f"\n⚠️  Invalid Callouts ({len(result.invalid_callouts)}):")
            for file_name, content, line in result.invalid_callouts[:5]:
                print(f"  • {file_name}:{line} → {content}")
        else:
            print(f"\n✅ No invalid callouts.")

        if result.warnings > 0:
            print(f"\n⚡ Warnings: {result.warnings}")

        print(f"\n{'='*55}")
        if result.is_clean:
            print(f"  ✅ VAULT IS HEALTHY")
        else:
            print(f"  🔴 ISSUES FOUND — run with --fix to auto-repair")
        print(f"{'='*55}\n")

    @staticmethod
    def json_output(data: dict):
        """Print JSON output."""
        print(json.dumps(data, indent=2, ensure_ascii=False))

    @staticmethod
    def status_report(
        vault: Optional[Path],
        doc_dirs: list[Path],
        result: Optional[ValidationResult],
        source_path: Optional[str] = None,
    ):
        """Print comprehensive status report."""
        print(f"\n{'='*55}")
        print(f"  🏛️  WIKI HEALTH REPORT")
        print(f"{'='*55}")

        if vault:
            detector_internal = VaultDetector(vault.parent)
            md_count = detector_internal.count_md_files(vault)
            print(f"\n📂 Vault:           {vault.name}/ ({md_count} .md files)")
            if result:
                print(f"📊 OFM compliance:  {result.compliance_pct:.0f}%")
        else:
            src = source_path or DEFAULT_VAULT
            print(f"\n📂 Vault:           {src}/ (does not exist)")
            print(f"📊 OFM compliance:  N/A")

        if doc_dirs:
            print(f"\n📚 Other doc dirs detected:")
            detector_internal = VaultDetector(Path.cwd())
            for d in doc_dirs:
                md = detector_internal.count_md_files(d)
                vault_name = vault.name if vault else None
                if d.name != vault_name:
                    print(f"  • {d.name}/ — {md} .md files")
                else:
                    print(f"  • {d.name}/ — {md} .md files ← active vault")
        else:
            print(f"\n📚 Other doc dirs: none")

        print(f"\n{'─'*55}")
        if vault and result and not result.is_clean:
            print(f"💡 Recommendation: run:")
            print(f"   validator.py check --fix    — auto-repair")
            print(f"   validator.py migrate         — migrate to OFM")
        elif not vault:
            print(f"💡 Recommendation: run:")
            print(f"   validator.py init            — create vault")
            if doc_dirs:
                for d in doc_dirs:
                    print(f"   validator.py merge --from={d.name}  — import from {d.name}/")
        else:
            print(f"💡 Vault is healthy. No action required.")

        print(f"{'='*55}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cmd_check(args):
    """validator.py check — Validate vault contents."""
    vault = _resolve_vault(args.path)
    if vault is None:
        print("⚠️  Vault not found. Run 'validator.py status' or 'validator.py init'.")
        sys.exit(0)

    validator = Validator(vault)
    result = validator.validate_all()

    formatter = Formatter()

    if args.fix:
        repairer = Repairer(vault, dry_run=False)
        fix_count = 0
        fix_count += repairer.fix_broken_links(result)
        fix_count += repairer.add_frontmatter(result)
        if fix_count > 0:
            print(f"\n🔧 Repairs applied: {fix_count}")
            # Re-validate after fixes
            result = validator.validate_all()
        else:
            print("\n✅ No fixes needed.")

    if args.json:
        formatter.json_output(result.to_dict())
    else:
        formatter.text_report(result, str(vault))

    sys.exit(0 if result.is_clean else 1)


def cmd_status(args):
    """validator.py status — Diagnose vault and repo documentation state."""
    detector = VaultDetector(Path.cwd())
    vault = detector.find_vault(args.path)
    doc_dirs = detector.find_doc_dirs()

    result = None
    if vault:
        validator = Validator(vault)
        result = validator.validate_all()

    formatter = Formatter()
    if args.json:
        data = {
            "vault": str(vault) if vault else None,
            "vault_md_count": detector.count_md_files(vault) if vault else 0,
            "doc_dirs": [str(d) for d in doc_dirs],
            "result": result.to_dict() if result else None,
        }
        formatter.json_output(data)
    else:
        formatter.status_report(vault, doc_dirs, result, source_path=args.path)


def cmd_init(args):
    """validator.py init — Create a new Obsidian vault."""
    vault_path = Path(args.path) if args.path else Path(DEFAULT_VAULT)

    if vault_path.exists():
        print(f"⚠️  {vault_path}/ already exists. Use 'validator.py check' to validate it.")
        sys.exit(1)

    migrator = Migrator(vault_path, dry_run=args.dry_run)
    created = migrator.init_vault()
    action = "Would create" if args.dry_run else "Created"
    print(f"✅ {action} {created} items in {vault_path}/")
    if not args.dry_run:
        print(f"📝 Now run: validator.py check --fix")


def cmd_migrate(args):
    """validator.py migrate — Convert wiki files to OFM compliance."""
    vault = _resolve_vault(args.path)
    if vault is None:
        print("⚠️  Vault not found. Run 'validator.py init' first.")
        sys.exit(1)

    validator = Validator(vault)
    result = validator.validate_all()

    if result.is_clean:
        print("✅ Wiki is already OFM-compliant. No migration needed.")
        sys.exit(0)

    if args.dry_run:
        print(f"\n📋 Migration preview for {vault}/:")
        print(f"  • {len(result.broken_links)} broken links to fix")
        print(f"  • {len(result.missing_frontmatter)} files need frontmatter")
        print(f"  • {len(result.orphans)} orphan files")
        print(f"\nRun without --dry-run to apply.")
        sys.exit(0)

    # Backup
    if args.backup:
        branch = f"backup/pre-migration-{datetime.now().strftime('%Y-%m-%d')}"
        try:
            subprocess.run(
                ["git", "branch", branch],
                capture_output=True, check=True
            )
            print(f"✅ Git branch created: {branch}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  Could not create git backup branch. Continuing anyway...")

    # Apply fixes
    repairer = Repairer(vault, dry_run=False)
    fixed = 0
    fixed += repairer.fix_broken_links(result)
    fixed += repairer.add_frontmatter(result)

    print(f"\n✅ Migration complete. {fixed} issues fixed.")
    print(f"📝 Run 'validator.py check' to verify.")


def cmd_merge(args):
    """validator.py merge — Merge docs/ content into vault."""
    if not args.from_dir:
        print("⚠️  Specify source: validator.py merge --from=docs")
        sys.exit(1)

    source = Path(args.from_dir)
    if not source.exists():
        print(f"⚠️  Source {source}/ does not exist.")
        sys.exit(1)

    vault = _resolve_vault(args.path)
    if vault is None:
        print("⚠️  Vault not found. Run 'validator.py init' first.")
        sys.exit(1)

    migrator = Migrator(vault, dry_run=args.dry_run)
    moved = migrator.merge_from(source)

    action = "Would move" if args.dry_run else "Merged"
    print(f"✅ {action} {moved} files from {source}/ → {vault}/")
    if not args.dry_run and moved > 0:
        print(f"📝 Run 'validator.py check --fix' to validate merged content.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_vault(path: Optional[str]) -> Optional[Path]:
    """Resolve vault path. Returns None if not found."""
    detector = VaultDetector(Path.cwd())
    vault = detector.find_vault(path)
    return vault


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Obsidian Vault Validator & Migration Tool",
        prog="obsidian_validator.py",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Validate vault contents")
    p_check.add_argument("--path", help=f"Vault path (default: {DEFAULT_VAULT}/)")
    p_check.add_argument("--fix", action="store_true", help="Auto-fix issues")
    p_check.add_argument("--json", action="store_true", help="JSON output")

    # status
    p_status = sub.add_parser("status", help="Diagnose vault and repo state")
    p_status.add_argument("--path", help=f"Vault path to check (default: {DEFAULT_VAULT}/)")
    p_status.add_argument("--json", action="store_true", help="JSON output")

    # init
    p_init = sub.add_parser("init", help="Create a new Obsidian vault")
    p_init.add_argument("--path", help=f"Vault path to create (default: {DEFAULT_VAULT}/)")
    p_init.add_argument("--dry-run", action="store_true", help="Preview without changes")

    # migrate
    p_migrate = sub.add_parser("migrate", help="Convert wiki files to OFM")
    p_migrate.add_argument("--path", help=f"Vault path (default: {DEFAULT_VAULT}/)")
    p_migrate.add_argument("--dry-run", action="store_true", help="Preview only")
    p_migrate.add_argument("--backup", action="store_true", help="Create git backup branch")

    # merge
    p_merge = sub.add_parser("merge", help="Merge docs/ into vault")
    p_merge.add_argument("--from", dest="from_dir", required=True, help="Source directory")
    p_merge.add_argument("--path", help=f"Target vault path (default: {DEFAULT_VAULT}/)")
    p_merge.add_argument("--dry-run", action="store_true", help="Preview without changes")

    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    commands = {
        "check": cmd_check,
        "status": cmd_status,
        "init": cmd_init,
        "migrate": cmd_migrate,
        "merge": cmd_merge,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
