#!/usr/bin/env python3

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

import os
import subprocess
from pathlib import Path
import argparse
import json
import re
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).parent.parent.parent.parent

def get_git_changes():
    files = []
    try:
        if not (REPO_ROOT / ".git").exists():
            return []
        # Try to get changes from last 5 commits
        try:
            res = subprocess.check_output(["git", "diff", "--name-only", "HEAD~5"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL)
            files.extend(res.decode().split("\n"))
        except Exception:
            # Fallback to all tracked files if HEAD~5 is too deep
            res = subprocess.check_output(["git", "ls-files"], cwd=REPO_ROOT)
            files.extend(res.decode().split("\n"))
            
        # Get untracked files
        untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=REPO_ROOT)
        files.extend(untracked.decode().split("\n"))
        
        return list(set([f for f in files if f]))
    except Exception as e:
        print(f"⚠️ Git error: {e}")
        return []

def get_documented_files():
    docs = []
    # Read ARCHITECTURE.md from .agent/
    arch = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if arch.exists():
        docs.append(arch.read_text(encoding='utf-8', errors='ignore'))
    
    # Read wiki
    wiki_dir = REPO_ROOT / "wiki"
    if wiki_dir.exists():
        for f in wiki_dir.glob("**/*.md"):
            try:
                docs.append(f.read_text(encoding='utf-8', errors='ignore'))
            except Exception:
                pass
            
    # Read Skill documentation
    skills_dirs = [
        REPO_ROOT / ".agent" / "skills",
        REPO_ROOT / ".agent" / ".shared"
    ]
    for skills_dir in skills_dirs:
        if skills_dir.exists():
            for f in skills_dir.glob("**/SKILL.md"):
                try:
                    docs.append(f.read_text(encoding='utf-8', errors='ignore'))
                except Exception:
                    pass

    return "\n".join(docs)

def check_arch_consistency():
    """Verify that all agents and skills listed in ARCHITECTURE.md actually exist."""
    arch_path = REPO_ROOT / "wiki" / "ARCHITECTURE.md"  # correct path
    if not arch_path.exists():
        # fallback to .agent/ARCHITECTURE.md
        arch_path = REPO_ROOT / ".agent" / "ARCHITECTURE.md"
    if not arch_path.exists():
        return []
    
    content = arch_path.read_text(encoding='utf-8')
    drifts = []
    
    # Split content by H2 headers (##) to isolate Agents from Skills
    sections = re.split(r'^## ', content, flags=re.MULTILINE)
    
    agent_dir = REPO_ROOT / ".agent" / "agents"
    # Skills can be in multiple locations
    skill_dirs = [
        REPO_ROOT / ".agent" / "skills",
        REPO_ROOT / ".agent" / ".shared"
    ]
    
    def skill_exists(name):
        return any((sd / name).is_dir() for sd in skill_dirs)

    for section in sections:
        header = section.split('\n')[0].lower()
        # Find names in the FIRST column of tables
        names = re.findall(r'^\|\s*`([\w-]+)`\s*\|', section, re.MULTILINE)
        
        # Section identification logic
        is_agents_section = "agent" in header and "lifecycle" not in header and "skill" not in header
        is_skills_section = "skill" in header
        
        if is_agents_section:
            for name in names:
                if name.lower() in ["agent", "agent-name"]: continue
                # Recursive search — agents can now live in subdirectories
                matches = list(agent_dir.rglob(f"{name}.md"))
                if not matches:
                    drifts.append(f"AGENT DRIFT: '{name}' listed in Agents table but missing in .agent/agents/")
        
        elif is_skills_section:
            for name in names:
                if name.lower() in ["skill", "skill-name"]: continue
                if not skill_exists(name):
                    drifts.append(f"SKILL DRIFT: '{name}' listed in Skills table but missing in {skill_dirs[0]} or {skill_dirs[1]}")

    return drifts

def detect_drift():
    changes = get_git_changes()
    docs_content = get_documented_files()
    
    drifts = check_arch_consistency()
    # Filter for important files (code, not assets/logs)
    monitored_exts = [".go", ".ts", ".tsx", ".py", ".js"]
    
    # Paths to ignore for drift detection — archived code is frozen, no doc monitoring needed
    ignored_paths = ["archive/", "scratch/"]
    
    for f in changes:
        path = Path(f)
        # Skip ignored paths
        if any(f.startswith(p) for p in ignored_paths):
            continue
            
        if path.suffix in monitored_exts and "test" not in f:
            # print(f"Checking {f}...") # Debug
            # Check if filename is mentioned in docs
            if path.name not in docs_content:
                drifts.append(f"FILE DRIFT: {f} (modified but not in docs)")
                
    return drifts

def run_drift_detection() -> dict:
    """Public API wrapper — returns structured drift report for programmatic callers.

    Canonical import interface; status_report.py and other consumers should
    call this instead of detect_drift() directly.
    """
    drifts = detect_drift()
    return {
        "drifts": drifts,
        "passed": len(drifts) == 0,
        "count": len(drifts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def close_resolved_cards(dry_run: bool = False) -> list[str]:
    """Close open fix-doc-drift task cards whose drift has disappeared.

    Scans tasks/*fix-doc-drift-*.md for 'FILE DRIFT: <path>' markers, re-checks
    whether the file is still missing from documentation, and moves resolved
    cards to tasks/done/ with a Resolution section. Returns list of actions.

    This closes the loop: drift_detector.py no longer only *creates* cards —
    it also *closes* them once the drift is gone.
    """
    tasks_dir = REPO_ROOT / "tasks"
    done_dir = tasks_dir / "done"
    docs_content = get_documented_files()
    actions: list[str] = []

    if not tasks_dir.exists():
        return actions

    today = datetime.now().strftime("%Y-%m-%d")
    for card in sorted(tasks_dir.glob("*fix-doc-drift-*.md")):
        text = card.read_text(encoding="utf-8", errors="replace")
        # Extract all FILE DRIFT: <path> markers from the card
        markers = re.findall(r"FILE DRIFT:\s*([^\s(]+)", text)
        if not markers:
            continue

        resolved = True
        for f in markers:
            # Drift is gone when the filename is documented OR the file no
            # longer exists (e.g. renamed/removed — nothing to document).
            path = REPO_ROOT / f
            if path.exists() and Path(f).name not in docs_content:
                resolved = False
                break

        if not resolved:
            continue

        # Drift resolved → move card to done/ with Resolution section
        if dry_run:
            actions.append(f"WOULD CLOSE: {card.name}")
            continue

        done_dir.mkdir(parents=True, exist_ok=True)
        destination = done_dir / card.name
        resolution = (
            "\n## Resolution [%s]\n"
            "**Status**: CLOSED\n"
            "**Closed by**: drift_detector.py auto-close (drift no longer present)\n\n"
            "The files referenced by this card are now documented (or no longer exist), "
            "so the drift is resolved.\n"
        ) % today
        destination.write_text(text.rstrip() + "\n" + resolution, encoding="utf-8")
        card.unlink()
        actions.append(f"CLOSED: {card.name}")

    return actions


def main():
    parser = argparse.ArgumentParser(description="Detect Documentation Drift")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--close", action="store_true",
                        help="Auto-close resolved fix-doc-drift task cards (drift no longer present)")
    parser.add_argument("--dry-run", action="store_true", help="With --close: show what would be closed")
    args = parser.parse_args()

    drifts = detect_drift()

    if args.format == "json":
        payload = {
            "drifts": drifts,
            "passed": len(drifts) == 0,
            "count": len(drifts),
        }
        if args.close:
            payload["closed_cards"] = close_resolved_cards(dry_run=args.dry_run)
        print(json.dumps(payload))
        return

    print("🔍 Checking for Documentation Drift (Code vs Wiki)...")
    if args.close:
        closed = close_resolved_cards(dry_run=args.dry_run)
        if closed:
            for c in closed:
                print(f"  🗂  {c}")
        elif not args.dry_run:
            print("  🗂  No open fix-doc-drift cards to close.")
    if drifts:
        print("\n⚠️  WARNING: Found modified files not mentioned in documentation:")
        for d in drifts:
            print(f"  - {d}")
        print("\nRecommendation: Update ARCHITECTURE.md or Wiki using 'wiki-architect' and 'analyst'.")
    else:
        print("✅ Documentation is in sync with recent code changes.")

if __name__ == "__main__":
    main()
