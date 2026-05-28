#!/usr/bin/env python3
"""
Policy Guardrail - AI Safety Audit
Enforces architectural and design policies (e.g., Purple Ban, Secret Scanning).

Inline API (for pipeline integration):
    violations = check_inline(text)   # list[dict], empty = clean
"""

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
import json
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"
_WATCHDOG_PATH = REPO_ROOT / ".agent" / "config" / "watchdog_rules.json"
_RULES_CACHE: dict = {}
_RULES_MTIME: float = 0.0
_WATCHDOG_MTIME: float = 0.0


# ============================================================================
#  INLINE CHECK API (used by GuardrailPipeline)
# ============================================================================

def _rules_path() -> Path:
    return REPO_ROOT / ".agent" / "config" / "policy_rules.json"


def _build_watchdog_patterns() -> list[dict]:
    """Convert watchdog_rules.json block-list into policy pattern dicts."""
    try:
        data = json.loads(_WATCHDOG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    block = data.get("dangerous_operations", {}).get("commands", {}).get("block", [])
    return [
        {
            "id": f"watchdog_{i:02d}",
            "regex": re.escape(pattern),
            "description": f"Watchdog block-listed command: {pattern}",
            "block_on_match": True,
            "_source": "watchdog_rules.json",
        }
        for i, pattern in enumerate(block)
        if pattern.strip()
    ]


def _merge_watchdog(rules: dict) -> dict:
    """Inject watchdog block-list into forbidden_commands if import flag is set."""
    if not rules.get("import_watchdog_commands", False):
        return rules

    imported = _build_watchdog_patterns()
    if not imported:
        return rules

    import copy
    rules = copy.deepcopy(rules)
    for cat in rules.get("categories", []):
        if cat.get("name") == "forbidden_commands":
            existing_ids = {p.get("id") for p in cat.get("patterns", [])}
            cat["patterns"] = cat.get("patterns", []) + [
                p for p in imported if p["id"] not in existing_ids
            ]
            return rules

    rules.setdefault("categories", []).append({
        "name": "forbidden_commands",
        "severity": "critical",
        "patterns": imported,
    })
    return rules


def _baseline_rules() -> dict:
    """Minimal safe rule set used when policy_rules.json is absent.

    Always includes the watchdog block-list so critical commands are
    never silently allowed even in degraded mode.
    """
    watchdog_patterns = _build_watchdog_patterns()
    categories = []
    if watchdog_patterns:
        categories.append({
            "name": "forbidden_commands",
            "severity": "critical",
            "patterns": watchdog_patterns,
        })
    return {"categories": categories, "_source": "baseline_fallback"}


def _load_rules() -> dict:
    global _RULES_CACHE, _RULES_MTIME, _WATCHDOG_MTIME
    rp = _rules_path()
    try:
        policy_mtime = os.path.getmtime(rp)
    except OSError:
        # policy_rules.json absent — emit observability signal and use baseline
        print(
            "[policy_guardrail] WARNING: policy_rules.json not found"
            " — guardrail running on baseline rules only (DEGRADED MODE)",
            file=sys.stderr,
        )
        _write_missing_config_signal()
        return _baseline_rules()
    try:
        watchdog_mtime = os.path.getmtime(_WATCHDOG_PATH)
    except OSError:
        watchdog_mtime = 0.0

    stale = (
        policy_mtime != _RULES_MTIME
        or watchdog_mtime != _WATCHDOG_MTIME
        or not _RULES_CACHE
    )
    if stale:
        try:
            raw = json.loads(rp.read_text())
            _RULES_CACHE = _merge_watchdog(raw)
            _RULES_MTIME = policy_mtime
            _WATCHDOG_MTIME = watchdog_mtime
        except (json.JSONDecodeError, OSError):
            _RULES_CACHE = _baseline_rules()
    return _RULES_CACHE


def _write_missing_config_signal() -> None:
    """Write a bus signal so status_report and CI can surface the absent config."""
    try:
        signal_path = BUS_DIR / "policy_report.json"
        BUS_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        data = {
            "status": "MISSING_CONFIG",
            "message": "policy_rules.json not found — guardrail in degraded mode",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        import json as _json
        signal_path.write_text(_json.dumps(data, indent=2))
    except Exception:
        pass


def check_inline(text: str) -> list[dict]:
    """Scan text against policy_rules.json (or baseline rules when absent).

    Returns list of violation dicts. Empty list means clean.
    """
    rules = _load_rules()
    violations: list[dict] = []
    for category in rules.get("categories", []):
        cat_name = category.get("name", "unknown")
        cat_severity = category.get("severity", "medium")
        for pattern in category.get("patterns", []):
            regex = pattern.get("regex", "")
            if not regex:
                continue
            try:
                match = re.search(regex, text, re.IGNORECASE)
            except re.error:
                continue
            if match:
                violations.append({
                    "rule_id": pattern.get("id", "unknown"),
                    "category": cat_name,
                    "severity": cat_severity,
                    "description": pattern.get("description", "Policy violation"),
                    "match": match.group(0)[:120],
                    "block_on_match": pattern.get("block_on_match", True),
                })
    return violations

# Policies
PURPLE_FORBIDDEN = [r"purple", r"violet", r"indigo", r"#800080", r"rgb\(128,\s*0,\s*128\)"]
SECRET_PATTERNS = [r"(?i)api[-_]?key", r"(?i)secret", r"(?i)token", r"xox[p|b|o|a]-[0-9]{12}"]

def check_purple_ban(content, file_ext):
    if file_ext not in ['.css', '.html', '.tsx', '.jsx']:
        return []
    
    issues = []
    for pattern in PURPLE_FORBIDDEN:
        if re.search(pattern, content, re.I):
            issues.append(f"Visual Policy: Forbidden color detected ({pattern})")
    return issues

def check_secrets(content):
    issues = []
    for pattern in SECRET_PATTERNS:
        # Simple heuristic to avoid false positives (e.g., descriptions of keys)
        matches = re.findall(rf"{pattern}\s*[:=]\s*['\"](\w+?)['\"]", content)
        if matches:
            issues.append(f"Security Policy: Potential secret/key leak detected ({pattern})")
    return issues

def check_prose_first(content, file_path):
    # Ignore fragments as they are part of a larger document
    if "wiki/fragments" in str(file_path):
        return []
        
    if "wiki" not in str(file_path) and "docs/adr" not in str(file_path):
        return []
    
    if "Intuition" not in content and "Mental Model" not in content:
        return ["Process Policy: Missing 'Intuition' section (Karpathy Prose-First method)"]
    return []

def main():
    print(f"\n{'='*60}")
    print(f"🛡️  POLICY GUARDRAIL - Compliance Engine")
    print(f"{'='*60}")
    
    violations = []
    # Audit changed files (heuristic: last 10 mins)
    for ext in ['*.html', '*.css', '*.tsx', '*.jsx', '*.md', '*.py']:
        for p in REPO_ROOT.glob(f"**/{ext}"):
            if "node_modules" in str(p) or ".git" in str(p): continue
            
            try:
                mtime = os.path.getmtime(p)
                if (datetime.now().timestamp() - mtime) < 600:
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    
                    issues = []
                    issues += check_purple_ban(content, p.suffix)
                    issues += check_secrets(content)
                    issues += check_prose_first(content, p)
                    
                    if issues:
                        violations.append({"file": str(p.relative_to(REPO_ROOT)), "issues": issues})
            except:
                continue

    if violations:
        print("🔴 ALERT: Policy violations found!")
        for v in violations:
            print(f"   📄 File: {v['file']}")
            for issue in v['issues']:
                print(f"      🚫 {issue}")
    else:
        print("✅ All policies are compliant.")

    # Export for status_report
    with open(BUS_DIR / "policy_report.json", "w") as f:
        json.dump({
            "status": "VIOLATION" if violations else "PASS",
            "violations": violations,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, f, indent=2)

if __name__ == "__main__":
    from datetime import datetime
    main()
