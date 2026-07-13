#!/usr/bin/env python3
"""
harness_validate.py — Companion script for the harness-development skill.

Validates a harness manifest against the HARNESS_CONTRACT.md schema
and the capability matrix. Run before committing harness changes.

Usage:
    python3 harness_validate.py [PATH_TO_MANIFEST]
    python3 harness_validate.py                                    # default: .agent/config/harnesses.yaml
    python3 harness_validate.py /path/to/harnesses.yaml --json
    python3 harness_validate.py /path/to/harnesses.yaml --capabilities /path/to/capabilities.yaml

Exit codes:
    0  manifest is valid
    1  manifest has issues
    2  configuration error (file missing, etc.)
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / ".agent" / "config" / "harnesses.yaml"
DEFAULT_CAPABILITIES = REPO_ROOT / ".agent" / "config" / "capabilities.yaml"

# Mirror of harness_run.py's validation (kept in sync manually)
REQUIRED_MANIFEST_KEYS = {
    "name", "binary", "description", "capabilities_required",
    "capabilities_granted", "sandbox", "args",
}
REQUIRED_SANDBOX_KEYS = {"required", "network", "filesystem", "env_passthrough", "timeout_s"}
SUPPORTED_VERSIONS = {"2.0.0"}


def _load_yaml(path: Path):
    try:
        import yaml
    except ImportError:
        print("❌ PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        sys.exit(2)
    if not path.exists():
        print(f"❌ Manifest not found: {path}", file=sys.stderr)
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _validate_entry(entry: dict) -> list[str]:
    errors = []
    missing = REQUIRED_MANIFEST_KEYS - set(entry.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")
    if entry.get("sandbox"):
        sb_missing = REQUIRED_SANDBOX_KEYS - set(entry["sandbox"].keys())
        if sb_missing:
            errors.append(f"Missing sandbox keys: {sorted(sb_missing)}")
        if not entry["sandbox"].get("required"):
            errors.append("sandbox.required must be true in v2 (no opt-out)")
    if not entry.get("capabilities_required"):
        errors.append("capabilities_required must list at least one cap")
    return errors


def _check_capability_linkage(manifest: list[dict], capabilities: dict) -> list[str]:
    """Check that every capability in harnesses.yaml is in the operations table."""
    errors = []
    operations = capabilities.get("operations", {})
    if not operations:
        return errors  # no matrix, can't check

    for harness in manifest:
        name = harness.get("name", "?")
        for cap in harness.get("capabilities_required", []) + harness.get("capabilities_granted", []):
            if cap not in operations.values():
                # Cap might be defined in role caps but not in operations table
                # This is fine, but worth a warning
                if not _cap_in_any_role(cap, capabilities):
                    errors.append(
                        f"harness '{name}' uses capability '{cap}' "
                        f"which is not in operations table or any role's caps"
                    )
    return errors


def _cap_in_any_role(cap: str, capabilities: dict) -> bool:
    for role_data in capabilities.get("roles", {}).values():
        for cap_entry in role_data.get("capabilities", []):
            if isinstance(cap_entry, dict) and cap_entry.get("cap") == cap:
                return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Validate harness manifest")
    p.add_argument("manifest", nargs="?", default=None, help="Path to harnesses.yaml")
    p.add_argument("--capabilities", default=None, help="Path to capabilities.yaml (for cross-check)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else DEFAULT_MANIFEST
    cap_path = Path(args.capabilities) if args.capabilities else DEFAULT_CAPABILITIES

    try:
        data = _load_yaml(manifest_path)
    except SystemExit:
        return 2

    # Schema check
    version = data.get("version")
    if version not in SUPPORTED_VERSIONS:
        msg = f"Unsupported version {version!r}"
        if args.json:
            print(json.dumps({"passed": False, "errors": [msg]}))
        else:
            print(f"❌ {msg}")
        return 1

    harnesses = data.get("harnesses", [])
    if not isinstance(harnesses, list):
        msg = "harnesses must be a list"
        if args.json:
            print(json.dumps({"passed": False, "errors": [msg]}))
        else:
            print(f"❌ {msg}")
        return 1

    errors = []
    for h in harnesses:
        errors.extend(_validate_entry(h))

    # Cross-check with capabilities matrix
    capabilities = {}
    if cap_path.exists():
        try:
            capabilities = _load_yaml(cap_path)
        except SystemExit:
            pass
    if capabilities:
        errors.extend(_check_capability_linkage(harnesses, capabilities))

    passed = len(errors) == 0

    if args.json:
        result = {
            "manifest_path": str(manifest_path),
            "manifest_version": version,
            "harness_count": len(harnesses),
            "harness_names": [h.get("name", "?") for h in harnesses],
            "errors": errors,
            "passed": passed,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 Harness manifest: {manifest_path.name} (v{version})")
        print(f"   Harnesses: {len(harnesses)}")
        for h in harnesses:
            print(f"   - {h.get('name', '?')}: {h.get('description', '?')[:60]}")
        if errors:
            print(f"\n   ❌ {len(errors)} issue(s):")
            for e in errors:
                print(f"      - {e}")
        else:
            print(f"\n   ✅ All harnesses valid.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
