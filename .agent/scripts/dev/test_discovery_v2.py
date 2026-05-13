
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
from pathlib import Path

# Add scripts dir and orchestration subdir to path (agent_auctioneer lives there)
_SCRIPTS = Path(__file__).resolve().parents[1]
for _p in [str(_SCRIPTS), str(_SCRIPTS / "orchestration")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agent_auctioneer import find_candidates

tasks = [
    "implement a new backend endpoint for user registration with postgres and nodejs",
    "create a beautiful landing page with react and nextjs",
    "fix git merge conflicts in the main branch",
    "write unit tests for the database module using clean-code principles",
    "perform a security audit using vulnerability-scanner"
]

for task in tasks:
    print(f"\n🔍 Task: {task}")
    candidates = find_candidates(task)
    if not candidates:
        print("   ❌ No candidates found")
    else:
        # Show top 2 candidates
        for c in candidates[:2]:
            print(f"   ✅ {c['id']} (Score: {c['score']}, Indicators: {c['indicators']})")
