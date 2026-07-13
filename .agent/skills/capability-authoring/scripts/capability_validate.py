#!/usr/bin/env python3
"""
capability_validate.py — Companion script for the capability-authoring skill.

Validates a capability matrix YAML against best practices and prints
a human-readable report. Use this BEFORE committing matrix changes.

Usage:
    python3 capability_validate.py [PATH_TO_MATRIX]
    python3 capability_validate.py                          # default: .agent/config/capabilities.yaml
    python3 capability_validate.py /path/to/matrix.yaml --json

Exit codes:
    0  matrix is valid
    1  matrix has issues
    2  configuration error (file missing, etc.)
"""
import argparse
import json
import sys
from pathlib import Path

# Reuse the audit logic from capability_audit.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "dev"))
import capability_audit as audit  # type: ignore


def main() -> int:
    p = argparse.ArgumentParser(description="Validate capabilities matrix (companion to capability_audit.py)")
    p.add_argument("matrix", nargs="?", default=None, help="Path to capabilities.yaml")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = p.parse_args()

    # Temporarily override MATRIX_PATH for the audit module
    if args.matrix:
        audit.MATRIX_PATH = Path(args.matrix)

    # Run the audit checks
    matrix = audit._load_yaml()
    checks = {
        "schema": audit.check_schema(matrix),
        "default_deny": audit.check_default_deny(matrix),
        "required_operations": audit.check_required_operations(matrix),
        "cap_drift": audit.check_cap_drift(matrix),
        "constraints": audit.check_constraints(matrix),
    }
    wildcards = audit.check_wildcards(matrix)
    all_issues = sum(checks.values(), [])
    total = len(all_issues) + len(wildcards)
    passed = len(all_issues) == 0 and (not wildcards or not args.strict)

    if args.json:
        result = {
            "matrix_path": str(audit.MATRIX_PATH),
            "matrix_version": matrix.get("version"),
            "checks": {k: v for k, v in checks.items() if v},
            "warnings": wildcards,
            "total_issues": total,
            "passed": passed,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 Capability matrix validation: {audit.MATRIX_PATH.name}")
        print(f"   Version: {matrix.get('version')}")
        print(f"   Status: {'✅ PASS' if passed else '❌ FAIL'}")
        print(f"   Issues: {len(all_issues)}, Warnings: {len(wildcards)}")
        for cat, issues in checks.items():
            if issues:
                print(f"\n   ❌ {cat}:")
                for i in issues:
                    print(f"      - {i}")
        if wildcards:
            print(f"\n   ⚠️  Wildcards:")
            for w in wildcards:
                print(f"      {w}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
