#!/usr/bin/env python3
"""
dry_run_distribute.py — B4: dry-run of the GitHub Actions distribute workflow.

Simulates the rsync steps from .github/workflows/distribute-agentic-kit.yml
WITHOUT pushing to any remote. Useful for:
- Pre-merge verification (does the new code make it to target repos?)
- Catching files that are accidentally excluded
- Estimating PR impact

Usage:
    python3 .agent/scripts/dev/dry_run_distribute.py [--target REPO] [--check-excludes]

Exit codes:
    0  dry-run passed (all expected files are present)
    1  dry-run failed (some expected files are missing)
    2  configuration error
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Exact exclude list from .github/workflows/distribute-agentic-kit.yml
RSYNC_EXCLUDES = [
    "--exclude=bus/",
    "--exclude=history/",
    "--exclude=brain/",
    "--exclude=data/",
    "--exclude=.shared/",
    "--exclude=rules/LESSONS_LEARNED.md",
    "--exclude=KNOWLEDGE.md",
    "--exclude=KNOWLEDGE_MAP.md",
    "--exclude=*.db",
    "--exclude=skill.lock",
    "--exclude=*.tmp",
    "--exclude=mcp-server-agent-kit/bin/",
]

# Files that MUST be present after rsync (regression check for the new epic).
# Note: paths are RELATIVE to the rsync source (no leading ".agent/" prefix).
EPIC_MUST_BE_PRESENT = [
    # STORY-3.3 SIGTERM Channel
    "scripts/orchestration/daemon/server.py",
    # STORY-2 INBOX v2
    "config/inbox.schema.json",
    "scripts/communication/inbox.py",
    "workflows/inbox.md",
    # STORY-4 Capability Matrix
    "config/capabilities.yaml",
    "scripts/permissions/capability_check.py",
    "scripts/dev/capability_audit.py",
    # STORY-5 Harness v2
    "config/harnesses.yaml",
    "HARNESS_CONTRACT.md",
    "scripts/harness/harness_run.py",
    # STORY-6 Knowledge Re-injection
    "scripts/communication/knowledge_inject.py",
    # STORY-1 Forcing Function
    "scripts/dev/git_pre_commit_distill.py",
    # Phase B: 4 persona
    "agents/specialists/runtime/harness-runner.md",
    "agents/specialists/runtime/permission-guard.md",
    "agents/specialists/runtime/knowledge-curator.md",
    "agents/specialists/runtime/inbox-attendant.md",
    # Phase B: 3 skills
    "skills/harness-development/SKILL.md",
    "skills/capability-authoring/SKILL.md",
    "skills/inbox-patterns/SKILL.md",
]


def _parse_rsync_output(out: str, prefix: str) -> set[str]:
    """Parse rsync --dry-run output and return set of file paths (without prefix)."""
    files = set()
    for line in out.splitlines():
        if not line or line.startswith("sending") or line.startswith("total"):
            continue
        if line.startswith(">") or line.startswith("<") or line.startswith("c"):
            parts = line.split()
            if parts:
                fn = parts[-1]
                if "/" in fn and fn != "./":
                    files.add(fn)
        else:
            line = line.rstrip("/")
            if line and line != "." and line != "./":
                files.add(line)
    return files


def run_rsync_dry_run() -> dict:
    """Simulate the rsync into a tempdir and return what would be sent."""
    with tempfile.TemporaryDirectory(prefix="distribute_dryrun_") as tmp:
        target = Path(tmp) / "target"
        target.mkdir()

        # 1. .agent folder
        cmd_agent = ["rsync", "-av", "--delete", "--dry-run", *RSYNC_EXCLUDES,
                     str(REPO_ROOT / ".agent") + "/", str(target / ".agent") + "/"]
        agent_result = subprocess.run(cmd_agent, capture_output=True, text=True)

        # 2. .claude/agents
        cmd_claude_agents = ["rsync", "-av", "--delete", "--dry-run",
                             str(REPO_ROOT / ".claude" / "agents") + "/",
                             str(target / ".claude" / "agents") + "/"]
        ca_result = subprocess.run(cmd_claude_agents, capture_output=True, text=True)

        # 3. .claude/commands
        cmd_claude_cmds = ["rsync", "-av", "--delete", "--dry-run",
                           str(REPO_ROOT / ".claude" / "commands") + "/",
                           str(target / ".claude" / "commands") + "/"]
        cc_result = subprocess.run(cmd_claude_cmds, capture_output=True, text=True)

        # 4. .opencode/agents
        cmd_oc_agents = ["rsync", "-av", "--delete", "--dry-run",
                         str(REPO_ROOT / ".opencode" / "agents") + "/",
                         str(target / ".opencode" / "agents") + "/"]
        oc_result = subprocess.run(cmd_oc_agents, capture_output=True, text=True)

        # Parse all outputs
        sent_files = set()
        for result, prefix in [
            (agent_result, ".agent/"),
            (ca_result, ".claude/agents/"),
            (cc_result, ".claude/commands/"),
            (oc_result, ".opencode/agents/"),
        ]:
            files = _parse_rsync_output(result.stdout, prefix)
            for f in files:
                sent_files.add(f)
        return {"sent": sent_files, "stdout": agent_result.stdout + ca_result.stdout}


def check_required_files(sent_files: set) -> tuple[list[str], list[str], list[str]]:
    """Check that all EPIC_MUST_BE_PRESENT files would be sent.

    Returns: (present_in_rsync, present_in_bin, missing)
    """
    # Files copied via explicit `cp` in the workflow (not via rsync)
    bin_files = {"bin/stop", "bin/inbox", "bin/harness_run"}
    bin_present = {bf for bf in bin_files if (REPO_ROOT / bf).exists()}

    missing = []
    present = []
    for rel in EPIC_MUST_BE_PRESENT:
        if rel in sent_files:
            present.append(rel)
        elif rel in bin_present:
            pass  # Will be reported separately
        else:
            missing.append(rel)
    return present, sorted(bin_present), missing


def main() -> int:
    p = argparse.ArgumentParser(prog="dry_run_distribute")
    p.add_argument("--target", help="Target repo name (for documentation only)")
    p.add_argument("--check-excludes", action="store_true",
                   help="Just check excludes, don't run rsync")
    p.add_argument("--list", action="store_true", help="List all files that would be sent")
    args = p.parse_args()

    if not args.check_excludes:
        print(f"🔍 Dry-run distribute from {REPO_ROOT}")
        if args.target:
            print(f"   Target: {args.target}")
        print()

    if shutil.which("rsync") is None:
        print("❌ rsync not installed. Install with: apt install rsync", file=sys.stderr)
        return 2

    if args.check_excludes:
        print("📋 Excludes in use:")
        for ex in RSYNC_EXCLUDES:
            print(f"   {ex}")
        return 0

    result = run_rsync_dry_run()
    sent = result["sent"]

    if args.list:
        print(f"📦 {len(sent)} files would be sent:")
        for f in sorted(sent):
            print(f"   {f}")
        return 0

    print(f"📊 Total files that would be sent: {len(sent)}")
    print()

    present, bin_present, missing = check_required_files(sent)
    total_checked = len(EPIC_MUST_BE_PRESENT)
    print(f"✅ Present in rsync ({len(present)}/{total_checked} epic files):")
    for f in present[:5]:
        print(f"   ✓ {f}")
    if len(present) > 5:
        print(f"   ... and {len(present) - 5} more")
    print()

    if bin_present:
        print(f"🛠️  Present in bin/ (explicit cp in workflow): {len(bin_present)}")
        for f in bin_present:
            print(f"   ✓ {f}")
        print()

    if missing:
        print(f"❌ MISSING ({len(missing)} epic files would NOT be sent):")
        for f in missing:
            print(f"   ✗ {f}")
        return 1

    print("🎉 All epic files would be sent correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
