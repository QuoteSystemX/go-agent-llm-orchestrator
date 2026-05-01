#!/usr/bin/env python3
"""Guardrail Monitor — Budget + Dangerous Operation + Protected File checks.

Validates agent actions against watchdog_rules.json before execution.
Called by the orchestrator before major operations.
"""
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

# Import from common lib
try:
    from lib.paths import WATCHDOG_RULES_PATH, TELEMETRY_PATH
    from lib.common import load_json_safe
except ImportError:
    # Fallback for direct execution if lib not in path
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import WATCHDOG_RULES_PATH, TELEMETRY_PATH
    from lib.common import load_json_safe

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
    """Check if a pattern matches a command using word-boundary-aware matching."""
    pat = pattern.strip().lower()
    cmd = command.strip().lower()

    if " " in pat:
        if _is_inside_string_search(cmd, pat):
            return False

        if pat.endswith("/") or pat.endswith("/*"):
            idx = cmd.find(pat)
            if idx >= 0:
                after = cmd[idx + len(pat):]
                if pat.endswith("/") and after and after[0] not in (" ", "\t", "|", ";", "&"):
                    return False
            return pat in cmd
        return pat in cmd
    else:
        if _is_inside_string_search(cmd, pat):
            return False
        regex = rf'\b{re.escape(pat)}\b'
        return bool(re.search(regex, cmd))

def _is_inside_string_search(cmd: str, pattern: str) -> bool:
    """Detect if the pattern appears inside a safe search/display context."""
    search_prefixes = ["grep ", "egrep ", "fgrep ", "rg ", "ag ", "ack ",
                       "cat ", "less ", "more ", "head ", "tail ",
                       "echo ", "printf ", "log "]
    for prefix in search_prefixes:
        if cmd.startswith(prefix):
            return True
    return False

def _split_commands(command: str) -> list[str]:
    """Split a complex command into individual segments (pipes, chains, subshells)."""
    # Simplified splitting - in a real shell this is much more complex
    # but for safety checks we want to be conservative.
    segments = re.split(r'[;|]|&&|\|\|', command)
    
    # Handle subshells $(...) and `...`
    subshells = re.findall(r'\$\((.*?)\)', command)
    subshells += re.findall(r'`(.*?)`', command)
    
    return [s.strip() for s in segments + subshells if s.strip()]

def check_dangerous_command(rules: dict, command: str) -> tuple[str, str]:
    """Check a command against block/warn lists, including segments."""
    dangerous = rules.get("dangerous_operations", {})
    commands_cfg = dangerous.get("commands", {})

    segments = _split_commands(command)
    for seg in segments:
        for pattern in commands_cfg.get("block", []):
            if _is_command_match(pattern, seg):
                return "block", f"BLOCKED: Segment '{seg}' matches block-pattern '{pattern}'"

        for pattern in commands_cfg.get("warn", []):
            if _is_command_match(pattern, seg):
                return "warn", f"WARNING: Segment '{seg}' matches warn-pattern '{pattern}'"

    return "ok", ""

def check_secret_leak(command: str) -> tuple[bool, str]:
    """Check if the command contains likely secrets."""
    secret_patterns = {
        "Generic Secret": r'(?i)(key|pass|secret|token|auth|pwd)[a-z0-9_]*[-=_ ]{1,3}[a-zA-Z0-9]{16,}',
        "AWS Access Key": r'AKIA[0-9A-Z]{16}',
        "AWS Secret Key": r'(?i)aws_secret_access_key.*[a-zA-Z0-9/+=]{40}',
        "Private Key": r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----',
        "Bearer Token": r'Bearer [a-zA-Z0-9\-\._~+/]+=*',
    }

    for name, pattern in secret_patterns.items():
        if re.search(pattern, command):
            return True, f"LIKELY SECRET DETECTED ({name}) in command."
    
    return False, ""

def check_protected_file(rules: dict, filepath: str) -> tuple[str, str]:
    """Check if a file is in the protected list."""
    dangerous = rules.get("dangerous_operations", {})
    protected_patterns = dangerous.get("files", {}).get("protected", [])

    for pattern in protected_patterns:
        if fnmatch(filepath, pattern) or fnmatch(filepath, f"**/{pattern}"):
            return "protected", f"PROTECTED FILE: '{filepath}' matches '{pattern}' — requires explicit confirmation"

    return "ok", ""

def run_in_sandbox(command: str) -> bool:
    """Run a command in a Docker sandbox (requires Docker)."""
    import subprocess
    print(f"🐳 SANDBOX: Executing '{command}' in isolated container...")
    try:
        # We use alpine for speed, mounting nothing for isolation
        # Note: This is a demo implementation. Real sandbox needs resource limits.
        docker_cmd = ["docker", "run", "--rm", "alpine:latest", "sh", "-c", command]
        result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=60)
        print(f"📦 Sandbox Output:\n{result.stdout}")
        if result.stderr:
            print(f"⚠️ Sandbox Stderr:\n{result.stderr}")
        return result.returncode == 0
    except FileNotFoundError:
        print("❌ SANDBOX FAILURE: Docker not found in system path.")
        return False
    except Exception as e:
        print(f"❌ SANDBOX FAILURE: {e}")
        return False

def main():
    rules = load_json_safe(WATCHDOG_RULES_PATH)
    telemetry = load_json_safe(TELEMETRY_PATH)
    exit_code = 0
    sandbox_mode = "--sandbox" in sys.argv

    if not rules:
        print("⚠️  No watchdog rules found. Skipping checks.")
        sys.exit(0)

    # ... (budget checks) ...
    budget_ok, budget_msg = check_budget(rules, telemetry)
    if not budget_ok:
        print(f"🛑 WATCHDOG: {budget_msg}")
        exit_code = 1
    else:
        print(f"✅ Budget: {budget_msg}")

    # Command check
    if "--check-cmd" in sys.argv:
        idx = sys.argv.index("--check-cmd")
        if idx + 1 < len(sys.argv):
            cmd = sys.argv[idx + 1]
            
            # Secret check first
            secret_detected, secret_msg = check_secret_leak(cmd)
            if secret_detected:
                print(f"⚠️  WATCHDOG: {secret_msg}")
            
            level, reason = check_dangerous_command(rules, cmd)
            if level == "block":
                print(f"🛑 {reason}")
                exit_code = 2
            elif level == "warn":
                print(f"⚠️  {reason}")
                if sandbox_mode:
                    success = run_in_sandbox(cmd)
                    if not success: exit_code = 2
            else:
                print(f"✅ Command safe: '{cmd}'")
                if sandbox_mode:
                    run_in_sandbox(cmd)

    # File check
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
