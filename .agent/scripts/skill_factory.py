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

def create_script(name, description):
    if not name.endswith(".py"):
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
