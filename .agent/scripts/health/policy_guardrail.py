#!/usr/bin/env python3
"""
Policy Guardrail - AI Safety Audit
Enforces architectural and design policies (e.g., Purple Ban, Secret Scanning).
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
