#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Antigravity Standard: Path Resolution
REPO_ROOT = Path(__file__).resolve().parents[3]

def check_cyrillic():
    """
    Search for Cyrillic characters in critical directories.
    Excludes binary files and specific patterns if needed.
    """
    print("🔍 Checking for Cyrillic characters...")
    
    # Critical directories to check
    dirs = [".agent", "docs", "wiki"]
    
    # Regex for Cyrillic: [a-zA-Z] - using escape sequences to avoid self-match
    # \u0400-\u04FF covers most Cyrillic characters
    pattern = '[\u0400-\u04FF]'
    
    found_issues = []
    
    for d in dirs:
        dir_path = REPO_ROOT / d
        if not dir_path.exists():
            continue
            
        try:
            # Use grep to find matches
            # -r: recursive
            # -P: perl-compatible regex
            # -n: line number
            # --exclude-dir: exclude certain dirs
            cmd = ["grep", "-rP", pattern, str(dir_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.stdout:
                lines = result.stdout.splitlines()
                for line in lines:
                    if "Binary file" in line:
                        continue
                    found_issues.append(line)
        except Exception as e:
            print(f"⚠️ Error checking {d}: {e}")

    if found_issues:
        print(f"❌ Found {len(found_issues)} Cyrillic artifacts:")
        for issue in found_issues[:10]:
            print(f"  {issue}")
        if len(found_issues) > 10:
            print(f"  ... and {len(found_issues) - 10} more.")
        return False
    
    print("✅ No Cyrillic artifacts found.")
    return True

def main():
    if not check_cyrillic():
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
