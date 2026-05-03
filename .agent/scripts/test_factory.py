#!/usr/bin/env python3
"""Test Factory — Generates basic unit test files for the given target.
"""
import sys
import os
from pathlib import Path

def generate_test(target_path: str):
    target = Path(target_path)
    if not target.exists():
        return f"❌ Target {target_path} not found."

    ext = target.suffix
    test_dir = target.parent / "tests"
    test_dir.mkdir(exist_ok=True)
    
    if ext == ".py":
        test_file = test_dir / f"test_{target.stem}.py"
        content = f"""import unittest
from {target.stem} import *

class Test{target.stem.capitalize()}(unittest.TestCase):
    def test_basic(self):
        # TODO: Implement tests for {target.name}
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
"""
    elif ext == ".go":
        test_file = target.parent / f"{target.stem}_test.go"
        content = f"""package {target.parent.name}

import "testing"

func Test{target.stem.capitalize()}(t *testing.T) {{
    // TODO: Implement tests for {target.name}
    if false {{
        t.Errorf("fail")
    }}
}}
"""
    else:
        return f"❌ Extension {ext} not supported for auto-generation."

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    return f"✅ Test file created: {test_file}"

def main():
    if len(sys.argv) < 2:
        print("Usage: test_factory.py <target_file>")
        sys.exit(1)
    
    print(generate_test(sys.argv[1]))

if __name__ == "__main__":
    main()
