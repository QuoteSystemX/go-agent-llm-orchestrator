
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
import json
from pathlib import Path

# Mapping: file extension/path -> role
FILE_TO_ROLE_MAP = {
    ".go": "backend-specialist",
    ".py": "backend-specialist",
    ".js": "frontend-specialist",
    ".ts": "frontend-specialist",
    ".sql": "database-architect",
    "auth": "security-auditor",
    "crypto": "security-auditor",
    "deploy": "devops-engineer",
    "docker": "devops-engineer",
    "test": "test-engineer"
}

def suggest_roles(affected_files):
    roles = set()
    for file_path in affected_files:
        # Check by extension
        ext = Path(file_path).suffix
        if ext in FILE_TO_ROLE_MAP:
            roles.add(FILE_TO_ROLE_MAP[ext])
        
        # Check by keywords in the path
        for key, role in FILE_TO_ROLE_MAP.items():
            if key in file_path.lower():
                roles.add(role)
                
    return list(roles)

if __name__ == "__main__":
    # Expects a list of files via stdin or argument
    if len(sys.argv) < 2:
        print("Usage: impact_to_roles.py <file1,file2...>")
        sys.exit(1)
        
    files = sys.argv[1].split(",")
    suggested = suggest_roles(files)
    
    print(json.dumps({
        "suggested_roles": suggested,
        "reasoning": f"Based on impact analysis of {len(files)} files."
    }, indent=2))
