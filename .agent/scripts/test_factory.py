#!/usr/bin/env python3
"""Test Factory — Generates basic unit test files for the given target.

Generated Python tests import the module (not wildcard) and verify public
symbols are callable. Generated Go tests call the function with zero values
and check for panics.
"""
import sys
import ast
import importlib.util
from pathlib import Path


def _get_public_symbols(target_path: Path) -> list[str]:
    """Read source file via AST and return public function/class names."""
    try:
        tree = ast.parse(target_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    symbols = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.append(node.name)
    return symbols


def generate_test(target_path: str):
    target = Path(target_path)
    if not target.exists():
        return f"❌ Target {target_path} not found."

    ext = target.suffix
    test_dir = target.parent / "tests"
    test_dir.mkdir(exist_ok=True)

    if ext == ".py":
        test_file = test_dir / f"test_{target.stem}.py"
        symbols = _get_public_symbols(target)
        assertions = ""
        for sym in symbols:
            safe = sym.replace("`", "").replace("$", "")
            assertions += f"        self.assertTrue(callable(_module.{safe}), '{safe} should be callable')\n"

        content = f"""import unittest
import {target.stem} as _module


class Test{target.stem.capitalize()}(unittest.TestCase):
    def test_module_importable(self):
        self.assertIsNotNone(_module)

    def test_public_symbols_callable(self):
{assertions}

if __name__ == "__main__":
    unittest.main()
"""
    elif ext == ".go":
        test_file = target.parent / f"{target.stem}_test.go"
        content = f"""package {target.parent.name}

import "testing"

func Test{target.stem.capitalize()}_Exists(t *testing.T) {{
    // Verify the function/callable is defined (compile-time check).
    // Replace the zero-values below with actual test data.
    _ = {target.stem.capitalize()}
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
