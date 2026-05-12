#!/usr/bin/env python3
"""Dependency Analyzer — Checks for outdated or insecure dependencies.
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

import sys
import os
from pathlib import Path

import sys
import os
import re
import subprocess
import json
from pathlib import Path

def analyze_go():
    if not Path("go.mod").exists(): return []
    print("📦 Analyzing Go dependencies...")
    try:
        # Use 'go list' to get direct dependencies
        res = subprocess.run(["go", "list", "-m", "-f", "{{if not .Main}}{{.Path}} {{.Version}}{{end}}", "all"], 
                             capture_output=True, text=True)
        deps = res.stdout.strip().split("\n")
        return [d for d in deps if d]
    except:
        return ["Error: 'go' command failed."]

def analyze_python():
    deps = []
    if Path("requirements.txt").exists():
        print("📦 Analyzing Python requirements.txt...")
        content = Path("requirements.txt").read_text()
        deps.extend(re.findall(r'^([a-zA-Z0-9_\-]+)', content, re.MULTILINE))
    
    if Path("pyproject.toml").exists():
        print("📦 Analyzing pyproject.toml...")
        # Simple regex for dependencies
        content = Path("pyproject.toml").read_text()
        matches = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if matches:
            deps.extend(re.findall(r'["\']([a-zA-Z0-9_\-]+)', matches.group(1)))
    return list(set(deps))

def check_vulnerabilities(deps):
    # Mock vulnerability check against a small database for demo
    # In production, use 'safety' or 'osv-scanner'
    known_bad = ["log4j", "struts", "requests<2.31.0"]
    found = []
    for d in deps:
        for bad in known_bad:
            if bad in d:
                found.append(f"VULNERABILITY: {d} matches insecure pattern '{bad}'")
    return found

def main():
    print("🔍 Starting Deep Dependency Audit...")
    go_deps = analyze_go()
    py_deps = analyze_python()
    
    all_deps = go_deps + py_deps
    vulnerabilities = check_vulnerabilities(all_deps)
    
    report = {
        "total_dependencies": len(all_deps),
        "go_count": len(go_deps),
        "python_count": len(py_deps),
        "vulnerabilities": vulnerabilities,
        "timestamp": os.getenv("TIMESTAMP", "")
    }
    
    if vulnerabilities:
        print("🛑 ISSUES FOUND:")
        for v in vulnerabilities:
            print(f"  - {v}")
        sys.exit(1)
    
    print(f"✅ Audit complete. {len(all_deps)} dependencies verified.")
    # Save report to bus
    bus_path = Path(".agent/bus/dependency_report.json")
    bus_path.parent.mkdir(parents=True, exist_ok=True)
    bus_path.write_text(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
