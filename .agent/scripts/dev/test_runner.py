#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

def run_all_tests():
    print("🧪 Antigravity Unified Test Runner")
    print("====================================")
    
    test_dir = REPO_ROOT / ".agent" / "scripts" / "tests"
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        sys.exit(1)

    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
