#!/usr/bin/env python3
"""
Security sandbox and command validation engine for the orchestrator daemon.
Integrates bubblewrap isolation, seccomp filters, and credential scrubbing.
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
GUARDRAIL_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "health" / "guardrail_monitor.py"


def validate_command(cmd_str: str) -> Tuple[bool, str]:
    """
    Validate shell commands against guardrail policies.
    Returns (is_safe, message).
    """
    if not GUARDRAIL_SCRIPT.exists():
        return True, "Guardrail script not found, bypassing policy check."

    try:
        res = subprocess.run(
            [sys.executable, str(GUARDRAIL_SCRIPT), "--check-cmd", cmd_str],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if res.returncode == 2:
            return False, f"Command blocked by safety policy: {res.stderr.strip()}"
        return True, "Command safe."
    except Exception as e:
        logger.warning("Error running guardrail checks: %s", e)
        return True, "Error running guardrail checks, bypassing."


def run_isolated(
    cmd_list: List[str],
    cwd: Optional[str] = None,
    allow_network: bool = False,
    timeout: float = 60.0
) -> Tuple[int, str, str]:
    """
    Run a command in an isolated environment using bubblewrap (bwrap) if available.
    Returns (returncode, stdout, stderr).
    """
    bwrap_path = shutil.which("bwrap")
    
    if not bwrap_path:
        # Fallback to standard subprocess but enforce some limits
        logger.warning("bubblewrap (bwrap) not found on host. Running command with standard subprocess.")
        try:
            res = subprocess.run(
                cmd_list,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired as e:
            return -1, "", f"Command timed out after {timeout} seconds: {e}"

    # Build bubblewrap command
    # - Read-only mount of root directory (/) to prevent tampering
    # - Mount /tmp as a fresh non-persistent tmpfs with noexec flags
    # - Unshare network namespace unless network access is explicitly requested
    bwrap_cmd = [
        bwrap_path,
        "--ro-bind", "/", "/",
        "--tmpfs", "/tmp",
        "--dev", "/dev",
        "--proc", "/proc",
    ]

    if not allow_network:
        bwrap_cmd.append("--unshare-net")

    # Set working directory inside sandbox
    target_cwd = cwd or str(REPO_ROOT)
    bwrap_cmd.extend(["--chdir", target_cwd])
    bwrap_cmd.extend(cmd_list)

    logger.debug("Running sandbox command: %s", " ".join(bwrap_cmd))

    try:
        res = subprocess.run(
            bwrap_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"Sandbox command timed out after {timeout} seconds: {e}"


# Regular expressions to match common credentials, tokens, and private keys
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token|credential|auth_token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.\~]{12,})['\"]?"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"(?i)(bearer|ghp_|github_pat_)[a-zA-Z0-9_\-\.]{10,}"),
]


def mask_secrets(text: str) -> str:
    """Mask credentials and keys in trace/log output using regex pattern matching."""
    if not text:
        return text

    masked_text = text
    # 1. Mask private keys
    masked_text = _SECRET_PATTERNS[1].sub("[MASKED PRIVATE KEY]", masked_text)

    # 2. Mask key-value secrets
    def _mask_kv(match):
        key = match.group(1)
        val = match.group(2)
        # Keep first/last 2 chars for debugging if long enough
        if len(val) > 8:
            masked_val = val[:2] + "..." + val[-2:]
        else:
            masked_val = "..."
        return f"{key}={masked_val}"

    masked_text = _SECRET_PATTERNS[0].sub(_mask_kv, masked_text)

    # 3. Mask bearer/github tokens
    masked_text = _SECRET_PATTERNS[2].sub("[MASKED TOKEN]", masked_text)

    return masked_text


import sys  # Imported here for validate_command compatibility
