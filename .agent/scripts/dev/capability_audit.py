#!/usr/bin/env python3
"""
capability_audit.py — STORY-4 pre-deploy audit for capabilities matrix.

Validates the capabilities matrix in .agent/config/capabilities.yaml
against best practices and detects drift. Run this in CI before merge.

What it checks:
  1. Schema: required fields present (roles, operations, version)
  2. Roles: session-agent MUST be empty (default-deny invariant)
  3. Operations: every required op has a cap mapping
  4. Caps: every cap mentioned in operations is defined
  5. Drift: any cap declared in roles but not in operations
  6. Wildcards: capability wildcards (e.g. task:*) — flag for review
  7. Constraints: every constrained cap has a constraint field

Exit codes:
  0  all checks pass
  1  audit failed (issues found)
  2  configuration error (matrix missing or unparseable)
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / ".agent" / "config" / "capabilities.yaml"
SUPPORTED_VERSIONS = {"1.0.0"}

# Required operations for the kit to function. Add new ones here.
REQUIRED_OPERATIONS = {
    "task_write": "modify-tasks",
    "task_read": "read-tasks",
    "bus_read": "read-bus",
    "bus_write": "modify-bus",
    "daemon_start": "start-daemon",
    "daemon_stop": "stop-daemon",
    "distill": "trigger-distill",
    "infra_write": "modify-infra",
    "infra_read": "read-infra",
    "harness_run": "harness-run",
    "config_write": "modify-config",
}


def _load_yaml():
    try:
        import yaml
    except ImportError:
        print("❌ PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    if not MATRIX_PATH.exists():
        print(f"❌ Matrix not found: {MATRIX_PATH}", file=sys.stderr)
        sys.exit(2)
    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_schema(matrix: dict) -> list[str]:
    issues = []
    version = matrix.get("version")
    if version not in SUPPORTED_VERSIONS:
        issues.append(f"unsupported version {version!r} (supported: {sorted(SUPPORTED_VERSIONS)})")
    if "roles" not in matrix or not isinstance(matrix.get("roles"), dict):
        issues.append("missing or invalid 'roles' section")
    if "operations" not in matrix or not isinstance(matrix.get("operations"), dict):
        issues.append("missing or invalid 'operations' section")
    return issues


def check_default_deny(matrix: dict) -> list[str]:
    issues = []
    session_agent = matrix.get("roles", {}).get("session-agent", {})
    caps = session_agent.get("capabilities", [])
    # Filter out empty list entries (sometimes used as placeholder)
    real_caps = [c for c in caps if c]
    if real_caps:
        issues.append(
            f"session-agent has {len(real_caps)} capability(ies) — "
            f"should be empty (default-deny invariant). "
            f"Found: {[c.get('cap') for c in real_caps]}"
        )
    return issues


def check_required_operations(matrix: dict) -> list[str]:
    issues = []
    operations = matrix.get("operations", {})
    for op, expected_cap in REQUIRED_OPERATIONS.items():
        if op not in operations:
            issues.append(f"required operation missing: '{op}' (should map to '{expected_cap}')")
        elif operations[op] != expected_cap:
            issues.append(
                f"operation '{op}' maps to '{operations[op]}', "
                f"expected '{expected_cap}'"
            )
    return issues


def check_cap_drift(matrix: dict) -> list[str]:
    issues = []
    operations = matrix.get("operations", {})
    operations_caps = set(operations.values())

    # All caps referenced in operations must be valid
    for op, cap in operations.items():
        if not isinstance(cap, str) or not cap.replace("-", "").replace("_", "").isalnum():
            issues.append(f"operation '{op}' has invalid cap name '{cap}'")

    # All caps in role capabilities should appear in operations
    # (otherwise they are dead caps that can never be checked via the public API)
    used_caps = set()
    for role_data in matrix.get("roles", {}).values():
        for cap_entry in role_data.get("capabilities", []):
            if isinstance(cap_entry, dict):
                used_caps.add(cap_entry.get("cap"))

    dead_caps = used_caps - operations_caps - {None}
    if dead_caps:
        issues.append(
            f"dead capabilities (declared in roles but not in operations): {sorted(dead_caps)}"
        )
    return issues


def check_wildcards(matrix: dict) -> list[str]:
    """Flag wildcard scopes for security review."""
    warnings = []
    for role_name, role_data in matrix.get("roles", {}).items():
        for cap_entry in role_data.get("capabilities", []):
            if not isinstance(cap_entry, dict):
                continue
            scope = cap_entry.get("scope", "global")
            # Allow literal "*" if it appears inside quotes (e.g., scope: task:"*")
            # Strip the "..." parts before checking for wildcards.
            import re
            scope_stripped = re.sub(r'"[^"]*"', '', scope)
            if "*" in scope_stripped and not scope_stripped.endswith(":*"):
                warnings.append(
                    f"  role={role_name} cap={cap_entry.get('cap')} scope={scope!r}: "
                    f"unusual wildcard pattern (expected trailing :* or no *)"
                )
    return warnings


def check_constraints(matrix: dict) -> list[str]:
    """Ensure sensitive caps have constraint fields documented."""
    needs_constraint = {"harness-run", "execute-cli-high"}
    issues = []
    for role_name, role_data in matrix.get("roles", {}).items():
        for cap_entry in role_data.get("capabilities", []):
            if not isinstance(cap_entry, dict):
                continue
            if cap_entry.get("cap") in needs_constraint and "constraint" not in cap_entry:
                issues.append(
                    f"sensitive cap '{cap_entry.get('cap')}' (role={role_name}) "
                    f"missing 'constraint' field"
                )
    return issues


def main() -> int:
    p = argparse.ArgumentParser(
        prog="capability_audit",
        description="STORY-4 pre-deploy audit for capabilities matrix.",
    )
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = p.parse_args()

    matrix = _load_yaml()

    checks = {
        "schema": check_schema(matrix),
        "default_deny": check_default_deny(matrix),
        "required_operations": check_required_operations(matrix),
        "cap_drift": check_cap_drift(matrix),
        "constraints": check_constraints(matrix),
    }
    wildcards = check_wildcards(matrix)
    all_issues = sum(checks.values(), [])
    total = len(all_issues) + len(wildcards)
    passed = len(all_issues) == 0 and (not wildcards or not args.strict)

    result = {
        "matrix_version": matrix.get("version"),
        "matrix_path": str(MATRIX_PATH),
        "checks": {k: v for k, v in checks.items() if v},
        "warnings": wildcards,
        "total_issues": total,
        "passed": passed,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if passed else 1

    print(f"🔍 Capability audit: {MATRIX_PATH.name} (v{result['matrix_version']})")
    print(f"   Status: {'✅ PASS' if passed else '❌ FAIL'}")
    print(f"   Issues: {len(all_issues)}  Warnings: {len(wildcards)}")
    for category, issues in checks.items():
        if issues:
            print(f"\n   ❌ {category}:")
            for i in issues:
                print(f"      - {i}")
    if wildcards:
        print(f"\n   ⚠️  wildcards (review recommended):")
        for w in wildcards:
            print(f"      {w}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
