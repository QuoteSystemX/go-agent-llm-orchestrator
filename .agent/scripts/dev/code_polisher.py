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
import sys
import subprocess
import argparse
import logging
from pathlib import Path
from lib.suppress import suppress
from lib.llm_client import query_llm_safe

logger = logging.getLogger(__name__)

POLISH_PROMPT = (
    "You are a senior code reviewer. Suggest exactly 2-3 concrete improvements "
    "for the following code. Focus on: readability, error handling, performance, "
    "and Python best practices. Output each suggestion as a bullet point with "
    "a short code snippet showing the improvement.\n\nCode:\n```\n{code}\n```"
)

def _apply_ruff_fix(path: str) -> bool:
    """Run ruff --fix on a single file. Returns True if fixes were applied."""
    with suppress("code_polisher.ruff_fix", level=logging.WARNING):
        res = subprocess.run(
            ["python3", "-m", "ruff", "check", "--fix", path],
            capture_output=True, text=True, timeout=30,
        )
        return "Fixed" in res.stdout or res.returncode == 0
    return False


def run_polish(dry_run: bool = True):
    print("💎 Starting Autonomous Code Polishing (Senior Excellence Loop)...")

    diff_files = []
    with suppress("code_polisher.git_diff", level=logging.WARNING):
        diff_files = subprocess.check_output(
            ['git', 'diff', '--name-only', 'main'], cwd=Path.cwd()
        ).decode().splitlines()

    if not diff_files:
        with suppress("code_polisher.glob_fallback", level=logging.DEBUG):
            diff_files = [str(f) for f in Path(".agent/scripts").rglob("*.py")]

    if not diff_files:
        print("✅ No files to polish.")
        return

    print(f"🧐 Analyzing {len(diff_files)} files for elegance...")
    total_suggestions = 0

    for f in diff_files[:10]:  # Limit to 10 files per run
        path = Path(f)
        if not path.exists() or not f.endswith(".py"):
            continue

        code = path.read_text(encoding="utf-8")[:3000]  # Truncate long files
        if len(code) < 50:
            continue

        print(f"  - Polishing: {f}")
        with suppress("code_polisher.llm_analysis", level=logging.ERROR):
            suggestion, src, _ = query_llm_safe(
                prompt=POLISH_PROMPT.format(code=code),
                model="auto",
                system_prompt="You are a senior Python code reviewer.",
                format_json=False,
            )
            if suggestion:
                total_suggestions += 1
                print(f"    💡 {suggestion.strip()[:200]}...")

    ruff_fixes = 0
    if not dry_run:
        print("\n🔧 Applying ruff auto-fixes...")
        for f in diff_files[:10]:
            if Path(f).exists() and f.endswith(".py") and _apply_ruff_fix(f):
                ruff_fixes += 1
                print(f"  ✅ ruff --fix applied: {f}")

    print(f"\n[POLISH COMPLETE — {total_suggestions} AI suggestion(s), {ruff_fixes} ruff fix(es) applied]")
    if dry_run:
        print("⚠️  Dry-run mode — no changes applied. Use --apply to run ruff auto-fixes.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-powered code polisher")
    parser.add_argument("--apply", action="store_false", dest="dry_run",
                        help="Apply suggested changes (default: dry-run)")
    args = parser.parse_args()
    run_polish(dry_run=args.dry_run)
