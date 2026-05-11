#!/usr/bin/env python3

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

import sys

def model_threats(intent: str):
    print(f"🛡️  Modeling Security Threats for: '{intent}'...")
    
    threats = {
        "login": ["Brute-force attack", "Session hijacking", "Credential stuffing"],
        "upload": ["RCE via malicious file", "Zip Slip", "Path traversal"],
        "database": ["SQL Injection", "Data exfiltration"],
        "api": ["Broken Object Level Authorization (BOLA)", "Mass assignment"]
    }
    
    found_threats = []
    for key, val in threats.items():
        if key in intent.lower():
            found_threats.extend(val)
            
    if found_threats:
        print("🚨 Potential Security Risks Detected:")
        for t in found_threats:
            print(f"  - {t}")
        print("\n💡 Mandatory Security AC added to the loop.")
    else:
        print("✅ No immediate security threats identified for this intent.")

if __name__ == "__main__":
    model_threats(" ".join(sys.argv[1:]))
