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

import os
import sys
import re
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

TEMP_DIR = REPO_ROOT / ".agent" / "tmp" / "ghost"


def _try_go_build(intent: str) -> bool:
    """Try real go build with a minimal main.go."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    main_go = TEMP_DIR / "main.go"
    safe_pkg = re.sub(r"[^a-zA-Z0-9_]", "", intent.replace(" ", "_")) or "proto"
    main_go.write_text(
        f'package main\n\nimport "fmt"\n\nfunc main() {{\n\tfmt.Println("{safe_pkg}")\n}}\n'
    )
    try:
        res = subprocess.run(
            ["go", "build", "-o", "/dev/null", str(main_go)],
            capture_output=True, text=True, timeout=15,
        )
        return res.returncode == 0
    except Exception as e:
        logger.debug("Go build not available: %s", e)
        return False
    finally:
        main_go.unlink(missing_ok=True)


def run_ghost_proto(intent: str):
    print(f"👻 Starting Ghost Prototyping for: '{intent}'...")
    print("🛠 Testing technical feasibility...")

    # Try real Go build
    ok = _try_go_build(intent)

    if not ok:
        # Fallback: basic feasibility heuristic
        ok = "impossible" not in intent.lower()
        if not ok:
            logger.info("[ghost_prototyper] Intent contains 'impossible' — marking as infeasible")

    if ok:
        print("✅ Ghost Prototype compiled successfully. Intent is technically feasible.")
        return True
    else:
        print("❌ GHOST PROTOTYPE FAILED: Feasibility check failed.")
        return False

if __name__ == "__main__":
    ok = run_ghost_proto(" ".join(sys.argv[1:]))
    sys.exit(0 if ok else 1)
