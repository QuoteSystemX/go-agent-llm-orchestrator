#!/usr/bin/env python3
"""
STORY-4 Capability Check — default-deny permission gate.

Loads .agent/config/capabilities.yaml and answers: is this role allowed
to perform this operation, in this scope?

Usage as a library:
    from capability_check import check, load_matrix
    matrix = load_matrix()
    if check(matrix, "session-agent", "harness_run", scope="task:abc"):
        ...  # allowed
    else:
        ...  # denied

Usage as a CLI:
    python3 capability_check.py --role session-agent --op harness_run
    # Exits 0 if allowed, 1 if denied.

Default-deny semantics:
    - If the role is not in the matrix, the operation is DENIED.
    - If the operation is not in the role's capabilities, DENIED.
    - If the scope doesn't match (e.g., role has repo:foo but caller is repo:bar), DENIED.
    - The session-agent role is INTENTIONALLY empty in the matrix.

Schema versioning:
    The YAML file has a `version` field. This module checks it against
    SUPPORTED_VERSIONS and refuses to load unsupported versions.
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / ".agent" / "config" / "capabilities.yaml"
SUPPORTED_VERSIONS = {"1.0.0"}

# Lazy yaml import (try the standard library or fall back to PyYAML)
try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


def _require_yaml():
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required for capability_check. "
            "Install with: pip install pyyaml"
        )


def load_matrix(path: Optional[Path] = None) -> dict:
    """Load and validate the capability matrix from YAML.

    Raises:
        FileNotFoundError: matrix file not found
        ValueError: matrix schema invalid or unsupported version
    """
    _require_yaml()
    p = path or MATRIX_PATH
    if not p.exists():
        raise FileNotFoundError(f"Capability matrix not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("Capability matrix must be a YAML mapping")
    version = data.get("version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported capability matrix version: {version!r}. "
            f"Supported: {sorted(SUPPORTED_VERSIONS)}"
        )
    if "roles" not in data or "operations" not in data:
        raise ValueError("Capability matrix must have 'roles' and 'operations'")
    return data


def _scope_matches(cap_scope: str, target_scope: str) -> bool:
    """Check if a granted scope covers the target scope.

    Examples:
        cap_scope="global", target_scope="repo:foo" -> True
        cap_scope="repo:foo", target_scope="repo:foo" -> True
        cap_scope="repo:foo", target_scope="repo:bar" -> False
        cap_scope="task:abc", target_scope="task:abc" -> True
        cap_scope="task:*", target_scope="task:abc" -> True (wildcard)
    """
    if cap_scope == "global":
        return True
    if cap_scope == target_scope:
        return True
    # Wildcard match: "task:*" matches "task:abc"
    if cap_scope.endswith(":*"):
        prefix = cap_scope[:-1]  # "task:"
        return target_scope.startswith(prefix)
    return False


def check(
    matrix: dict,
    role: str,
    operation: str,
    scope: Optional[str] = None,
) -> bool:
    """Return True if the role is allowed to perform the operation.

    Args:
        matrix: from load_matrix()
        role: one of the keys in matrix["roles"]
        operation: one of the keys in matrix["operations"]
        scope: target scope (e.g., "repo:foo", "task:abc"). If None, global.

    Returns:
        True if allowed, False if denied (default-deny).
    """
    target_scope = scope or "global"

    # Resolve operation → capability name
    cap_name = matrix.get("operations", {}).get(operation)
    if not cap_name:
        return False  # unknown operation = deny

    # Look up role's capabilities
    role_data = matrix.get("roles", {}).get(role)
    if not role_data:
        return False  # unknown role = deny

    caps = role_data.get("capabilities", [])
    for cap_entry in caps:
        if not isinstance(cap_entry, dict):
            continue
        if cap_entry.get("cap") != cap_name:
            continue
        if _scope_matches(cap_entry.get("scope", "global"), target_scope):
            return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(
        prog="capability_check",
        description="STORY-4 default-deny capability check.",
    )
    p.add_argument("--role", required=True, help="Agent role (infra-agent, squad-agent, session-agent, human)")
    p.add_argument("--op", required=True, help="Operation key (e.g., harness_run, modify-tasks)")
    p.add_argument("--scope", default=None, help="Target scope (e.g., repo:foo, task:abc)")
    args = p.parse_args()

    try:
        matrix = load_matrix()
    except Exception as e:
        print(f"❌ Failed to load capability matrix: {e}", file=sys.stderr)
        return 2

    allowed = check(matrix, args.role, args.op, args.scope)
    if allowed:
        print(f"✅ ALLOW: role={args.role} op={args.op} scope={args.scope or 'global'}")
        return 0
    else:
        print(f"❌ DENY:  role={args.role} op={args.op} scope={args.scope or 'global'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
