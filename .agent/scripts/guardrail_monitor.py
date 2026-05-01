#!/usr/bin/env python3
"""Guardrail Monitor — Budget + Dangerous Operation + Protected File checks.

Validates agent actions against watchdog_rules.json before execution.
Called by the orchestrator before major operations.

Usage:
    python3 guardrail_monitor.py                    # budget check only
    python3 guardrail_monitor.py --check-cmd "rm -rf /tmp/old"
    python3 guardrail_monitor.py --check-file ".env.production"
"""
import json
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
TELEMETRY_PATH = REPO_ROOT / ".agent" / "bus" / "telemetry.json"
RULES_PATH = REPO_ROOT / ".agent" / "config" / "watchdog_rules.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def check_budget(rules: dict, telemetry: dict) -> tuple[bool, str]:
    """Check token and cost limits."""
    limits = rules.get("limits", {})

    total_tokens = telemetry.get("total_tokens", 0)
    total_cost = telemetry.get("total_cost_usd", 0)

    if total_tokens > limits.get("token_budget_per_task", 100000):
        return False, f"TOKEN BUDGET EXCEEDED: {total_tokens} > {limits['token_budget_per_task']}"

    if total_cost > limits.get("cost_limit_per_task_usd", 2.0):
        return False, f"COST LIMIT EXCEEDED: ${total_cost:.2f} > ${limits['cost_limit_per_task_usd']:.2f}"

    return True, "Budget within limits."


def _is_command_match(pattern: str, command: str) -> bool:
    """Check if a pattern matches a command using word-boundary-aware matching.

    Rules:
    - Patterns that look like full commands (contain spaces) are matched
      as prefixes of the command string (after stripping).
    - Single-word patterns use word-boundary regex to avoid false positives
      like matching "DROP TABLE" inside a grep command searching for that string.
    """
    pat = pattern.strip().lower()
    cmd = command.strip().lower()

    if " " in pat:
        # Multi-word pattern: check if command starts with it or has it as a
        # standalone segment (not inside quotes or after grep/cat/echo)
        if _is_inside_string_search(cmd, pat):
            return False

        # For path-sensitive patterns like "rm -rf /", ensure the path
        # isn't just a prefix of a longer path (e.g., "/tmp/old")
        if pat.endswith("/") or pat.endswith("/*"):
            # Exact path block: "rm -rf /" should not match "rm -rf /tmp/old"
            # Check if what follows the pattern is end-of-string or whitespace
            idx = cmd.find(pat)
            if idx >= 0:
                after = cmd[idx + len(pat):]
                # If pattern ends with / and there's more path after it, not a match
                if pat.endswith("/") and after and after[0] not in (" ", "\t", "|", ";", "&"):
                    return False
            return pat in cmd
        return pat in cmd
    else:
        # Single-word pattern: word-boundary match, exclude string search context
        if _is_inside_string_search(cmd, pat):
            return False
        regex = rf'\b{re.escape(pat)}\b'
        return bool(re.search(regex, cmd))


def _is_inside_string_search(cmd: str, pattern: str) -> bool:
    """Detect if the pattern appears inside a safe search/display context.

    Avoids false positives like: grep "DROP TABLE" docs.md
    or: cat file.sql | grep "rm -rf"
    """
    # Common search/display commands where the pattern is an argument, not action
    search_prefixes = ["grep ", "egrep ", "fgrep ", "rg ", "ag ", "ack ",
                       "cat ", "less ", "more ", "head ", "tail ",
                       "echo ", "printf ", "log "]
    for prefix in search_prefixes:
        if cmd.startswith(prefix):
            return True

    # Note: We removed the global quote check because it blocked execution
    # contexts like psql -c 'DROP DATABASE'. We rely on prefix detection.
    return False


def check_dangerous_command(rules: dict, command: str) -> tuple[str, str]:
    """Check a command against block/warn lists.

    Returns:
        ("block", reason) — command must NOT execute.
        ("warn", reason) — command is risky, log and continue.
        ("ok", "") — command is safe.
    """
    dangerous = rules.get("dangerous_operations", {})
    commands_cfg = dangerous.get("commands", {})

    for pattern in commands_cfg.get("block", []):
        if _is_command_match(pattern, command):
            return "block", f"BLOCKED: '{command}' matches block-pattern '{pattern}'"

    for pattern in commands_cfg.get("warn", []):
        if _is_command_match(pattern, command):
            return "warn", f"WARNING: '{command}' matches warn-pattern '{pattern}'"

    return "ok", ""


def check_protected_file(rules: dict, filepath: str) -> tuple[str, str]:
    """Check if a file is in the protected list.

    Returns:
        ("protected", reason) — file requires explicit confirmation.
        ("ok", "") — file is not protected.
    """
    dangerous = rules.get("dangerous_operations", {})
    protected_patterns = dangerous.get("files", {}).get("protected", [])

    for pattern in protected_patterns:
        if fnmatch(filepath, pattern) or fnmatch(filepath, f"**/{pattern}"):
            return "protected", f"PROTECTED FILE: '{filepath}' matches '{pattern}' — requires explicit confirmation"

    return "ok", ""


def main():
    rules = load_json(RULES_PATH)
    telemetry = load_json(TELEMETRY_PATH)
    exit_code = 0

    if not rules:
        print("⚠️  No watchdog rules found. Skipping checks.")
        sys.exit(0)

    # Budget check (always runs)
    budget_ok, budget_msg = check_budget(rules, telemetry)
    if not budget_ok:
        print(f"🛑 WATCHDOG: {budget_msg}")
        exit_code = 1
    else:
        print(f"✅ Budget: {budget_msg}")

    # Command check (--check-cmd "command string")
    if "--check-cmd" in sys.argv:
        idx = sys.argv.index("--check-cmd")
        if idx + 1 < len(sys.argv):
            cmd = sys.argv[idx + 1]
            level, reason = check_dangerous_command(rules, cmd)
            if level == "block":
                print(f"🛑 {reason}")
                exit_code = 2
            elif level == "warn":
                print(f"⚠️  {reason}")
            else:
                print(f"✅ Command safe: '{cmd}'")

    # File check (--check-file "path/to/file")
    if "--check-file" in sys.argv:
        idx = sys.argv.index("--check-file")
        if idx + 1 < len(sys.argv):
            fpath = sys.argv[idx + 1]
            level, reason = check_protected_file(rules, fpath)
            if level == "protected":
                print(f"⚠️  {reason}")
                exit_code = 3
            else:
                print(f"✅ File not protected: '{fpath}'")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
