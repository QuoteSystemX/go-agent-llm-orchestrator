#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

# Ensure we can import from lib
sys.path.append(str(Path(__file__).resolve().parent))
from lib.paths import REPO_ROOT

SCRIPT_TEMPLATE = """#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.common import load_json_safe, save_json_atomic
from lib.paths import REPO_ROOT

def main():
    parser = argparse.ArgumentParser(description="{description}")
    args = parser.parse_args()
    
    # [YOUR LOGIC HERE]
    print("🚀 Tool {name} is running...")

if __name__ == "__main__":
    main()
"""

TEST_TEMPLATE = """#!/usr/bin/env python3
import unittest
import subprocess
import sys
from pathlib import Path

# Antigravity Standard: Path Resolution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / ".agent" / "scripts" / "{script_name}"

class Test{class_name}(unittest.TestCase):
    def test_help_output(self):
        \"\"\"Basic test to verify the script runs and shows help.\"\"\"
        res = subprocess.run([sys.executable, str(SCRIPT_PATH), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

if __name__ == "__main__":
    unittest.main()
"""

GO_TEST_TEMPLATE = """package {package_name}

import "testing"

func Test{class_name}(t *testing.T) {
    // TODO: Implement tests for {script_name}
    if false {
        t.Errorf("scaffold failed")
    }
}
"""

def create_script(name, description):
    if not name.endswith(".py") and not name.endswith(".go"):
        name += ".py"
        
    scripts_dir = REPO_ROOT / ".agent" / "scripts"
    target_path = scripts_dir / name
    
    if target_path.exists():
        print(f"❌ Script already exists: {name}")
        return False
        
    content = SCRIPT_TEMPLATE.format(name=name, description=description)
    target_path.write_text(content, encoding="utf-8")
    
    # Make executable
    os.chmod(target_path, 0o755)
    
    print(f"✅ Created script: {target_path}")
    
    # Create Test
    test_name = f"test_{name}"
    tests_dir = REPO_ROOT / ".agent" / "tests"
    tests_dir.mkdir(exist_ok=True)
    test_path = tests_dir / test_name
    
    class_name = "".join(x.capitalize() for x in name.replace(".py", "").replace(".go", "").split("_"))
    
    if name.endswith(".go"):
        # Go tests live next to the file
        test_name = f"{name.replace('.go', '')}_test.go"
        test_path = target_path.parent / test_name
        # Simple package name detection
        package_name = target_path.parent.name
        test_content = GO_TEST_TEMPLATE.format(script_name=name, class_name=class_name, package_name=package_name)
    else:
        # Python tests live in .agent/tests
        test_name = f"test_{name}"
        tests_dir = REPO_ROOT / ".agent" / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_path = tests_dir / test_name
        test_content = TEST_TEMPLATE.format(script_name=name, class_name=class_name)
    
    test_path.write_text(test_content, encoding="utf-8")
    
    print(f"✅ Created test: {test_path}")
    print(f"💡 Now run 'python3 .agent/scripts/doc_healer.py' to register it.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Skill Factory - Scaffolds new agentic tools.")
    parser.add_argument("name", help="Name of the script (e.g., log_parser.py)")
    parser.add_argument("description", help="What this tool does")
    args = parser.parse_args()
    
    create_script(args.name, args.description)

if __name__ == "__main__":
    main()
