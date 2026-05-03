#!/usr/bin/env python3
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
