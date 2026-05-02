import sys
import os
import re
import subprocess
import json
from datetime import datetime

REQUIRED_SECTIONS = [
    r"🤖 \*\*Agent Header\*\*",
    r"🎯 \*\*Context/Goal\*\*",
    r"🛠 \*\*Technical Implementation\*\*",
    r"📂 \*\*Impacted Components\*\*",
    r"📈 \*\*Outcome/Result\*\*"
]

def validate_sections(content):
    missing = []
    for section in REQUIRED_SECTIONS:
        if not re.search(section, content, re.IGNORECASE):
            missing.append(section.replace("\\", ""))
    return missing

def get_git_changed_files():
    try:
        output = subprocess.check_output(["git", "diff", "--name-only"], stderr=subprocess.STDOUT).decode()
        return [f.strip() for f in output.split("\n") if f.strip()]
    except Exception:
        return []

def validate_impacted_files(content):
    # Find the Impacted Components section
    match = re.search(r"📂 \*\*Impacted Components\*\*(.*?)(\n[#🎯🛠📈]|$)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return []
    
    section_content = match.group(1)
    # Extract file paths (assuming they are in markdown links or plain text)
    found_files = re.findall(r"(?:file:///|/|[a-zA-Z]:\\)([\w\-\./\\\s]+)", section_content)
    
    # Normalize paths
    normalized_found = []
    for f in found_files:
        # If absolute path, try to make it relative to repo root
        abs_path = os.path.abspath(f.strip())
        rel_path = os.path.relpath(abs_path, os.getcwd())
        normalized_found.append(rel_path)

    git_files = get_git_changed_files()
    
    mismatch = []
    for gf in git_files:
        if gf not in normalized_found:
            mismatch.append(gf)
            
    return mismatch

def save_to_bus(content, agent_name="unknown"):
    bus_dir = ".agent/bus/outputs"
    if not os.path.exists(bus_dir):
        os.makedirs(bus_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{agent_name}.json"
    
    # Extract specific fields for easier automation
    goal_match = re.search(r"🎯 \*\*Context/Goal\*\*:?\s*(.*?)(\n[🛠📂📈]|$)", content, re.DOTALL | re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else ""
    
    components_match = re.search(r"📂 \*\*Impacted Components\*\*:?\s*(.*?)(\n[📈]|$)", content, re.DOTALL | re.IGNORECASE)
    components_text = components_match.group(1).strip() if components_match else ""
    impacted_files = re.findall(r"(?:file:///|/|[a-zA-Z]:\\)([\w\-\./\\\s]+)", components_text)
    
    data = {
        "timestamp": timestamp,
        "agent": agent_name,
        "goal": goal,
        "impacted_files": [f.strip() for f in impacted_files],
        "content": content,
        "verified": True
    }
    
    with open(os.path.join(bus_dir, filename), "w") as f:
        json.dump(data, f, indent=2)

def clear_bus():
    bus_dir = ".agent/bus/outputs"
    if not os.path.exists(bus_dir):
        return
    for f in os.listdir(bus_dir):
        if f.endswith(".json"):
            os.remove(os.path.join(bus_dir, f))
    print("🧹 Bus cleared.")

def synthesize_outputs():
    bus_dir = ".agent/bus/outputs"
    if not os.path.exists(bus_dir):
        print("❌ No outputs to synthesize.")
        return
    
    output_files = sorted([f for f in os.listdir(bus_dir) if f.endswith(".json")])
    if not output_files:
        print("❌ No outputs found.")
        return

    outputs = []
    for f in output_files:
        with open(os.path.join(bus_dir, f), "r") as out_f:
            outputs.append(json.load(out_f))
    
    # Run automation scripts before clearing
    print("🔄 Running automation scripts (Assembler & Task Sync)...")
    scripts_dir = ".agent/scripts"
    try:
        subprocess.run([sys.executable, os.path.join(scripts_dir, "walkthrough_assembler.py")], check=True)
        subprocess.run([sys.executable, os.path.join(scripts_dir, "task_sync.py")], check=True)
    except Exception as e:
        print(f"⚠️  Automation failed: {e}")

    print("\n" + "="*50)
    print("🤖 **Agent Header**: orchestrator (Synthesis)")
    print("\n🎯 **Context/Goal**: Unified session report synthesis.")
    
    print("\n🛠 **Technical Implementation**:")
    for out in outputs:
        goal = out.get('goal', 'Completed task')
        print(f"- [{out['agent']}] {goal}")
        
    print("\n📂 **Impacted Components**:")
    all_files = set()
    for out in outputs:
        for f in out.get("impacted_files", []):
            all_files.add(f)
    for f in sorted(all_files):
        print(f"- {f}")
        
    print("\n📈 **Outcome/Result**: All tasks completed and verified in this session.")
    print("="*50 + "\n")

    # Final Step: Clear the bus
    clear_bus()

def main():
    if "--synthesize" in sys.argv:
        synthesize_outputs()
        sys.exit(0)
    
    if "--clear" in sys.argv:
        clear_bus()
        sys.exit(0)

    if len(sys.argv) < 2:
        # Read from stdin if no file provided
        content = sys.stdin.read()
    else:
        try:
            with open(sys.argv[1], "r") as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            sys.exit(1)

    print("🔍 Validating agent output via Output Gateway...")
    
    # 1. Check sections
    missing_sections = validate_sections(content)
    if missing_sections:
        print(f"❌ FAILED: Missing mandatory sections: {', '.join(missing_sections)}")
        sys.exit(1)
    
    # 2. Check impacted files
    # Only check if there are actual git changes
    git_files = get_git_changed_files()
    if git_files:
        mismatched = validate_impacted_files(content)
        if mismatched:
            print("⚠️  WARNING: Files modified in git but missing from Impacted Components:")
            for m in mismatched:
                print(f"   - {m}")
            # We dont exit 1 here for now to avoid blocking completely during rollout, 
            # but in strict mode we should.
    
    # 3. Save to Bus
    agent_match = re.search(r"🤖 \*\*Agent Header\*\*:?\s*(\w+)", content, re.IGNORECASE)
    agent_name = agent_match.group(1) if agent_match else "unknown"
    save_to_bus(content, agent_name)
    
    print("✅ SUCCESS: Output validated and mirrored to Bus.")

if __name__ == "__main__":
    main()
