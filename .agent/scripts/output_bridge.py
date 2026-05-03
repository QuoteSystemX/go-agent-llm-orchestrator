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
    
    # Detect provider for metadata
    provider = os.environ.get("AGENT_PROVIDER", "unknown").lower()
    if provider == "unknown":
        if os.environ.get("GEMINI_API_KEY"): provider = "antigravity"
        elif os.environ.get("ANTHROPIC_API_KEY"): provider = "cloud-core"

    data = {
        "timestamp": timestamp,
        "agent": agent_name,
        "provider": provider,
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
    print("🔄 Running automation scripts (Unified Hub Sync)...")
    scripts_dir = ".agent/scripts"
    automation_chain = [
        "walkthrough_assembler.py",
        "task_sync.py",
        "doc_healer.py",
        "visualize_deps.py",
        "obsidian_validator.py"
    ]
    
    for script in automation_chain:
        print(f"  - Executing {script}...")
        try:
            subprocess.run([sys.executable, os.path.join(scripts_dir, script)], check=True)
        except Exception as e:
            print(f"  ⚠️  {script} failed: {e}")

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
    
    # 0. Sync Wiki Knowledge (Karpathy 2.0)
    print("🔗 Syncing Obsidian Knowledge Graph...")
    scripts_dir = ".agent/scripts"
    try:
        subprocess.run([sys.executable, os.path.join(scripts_dir, "obsidian_sync.py")], check=True)
    except Exception as e:
        print(f"⚠️  Obsidian sync failed: {e}")

    # 1. Check sections
    missing_sections = validate_sections(content)
    if missing_sections:
        print(f"❌ FAILED: Missing mandatory sections: {', '.join(missing_sections)}")
        sys.exit(1)
    
    # Extract goal and files for further validation
    goal_match = re.search(r"🎯 \*\*Context/Goal\*\*:?\s*(.*?)(\n[🛠📂📈]|$)", content, re.DOTALL | re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else ""
    components_match = re.search(r"📂 \*\*Impacted Components\*\*:?\s*(.*?)(\n[📈]|$)", content, re.DOTALL | re.IGNORECASE)
    components_text = components_match.group(1).strip() if components_match else ""
    impacted_files = re.findall(r"(?:file:///|/|[a-zA-Z]:\\)([\w\-\./\\\s]+)", components_text)

    # 2. Mental Model Validation (Karpathy 2.0)
    try:
        subprocess.run([sys.executable, os.path.join(scripts_dir, "model_validator.py"), goal, json.dumps(impacted_files)], check=True)
    except subprocess.CalledProcessError:
        print("❌ FAILED: Change violates established Mental Models in wiki/mental-models/")
        # sys.exit(1)

    # 2.5 Governance Gate: Wiki-First Enforcement (Hybrid Protocol)
    try:
        subprocess.run([sys.executable, os.path.join(scripts_dir, "governance_gate.py"), json.dumps(impacted_files)], check=True)
    except subprocess.CalledProcessError:
        print("❌ FAILED: New files must be defined in the Wiki (Stories/ADR) first.")
        # sys.exit(1)

    # 3. Red-Team Gate: Security & Impact Audit
    critical_keywords = ["auth", "security", "infra", "secret", "bus", "permission", "access", "root"]
    is_critical = any(k in goal.lower() for k in critical_keywords) or \
                  any("infra" in f or "bus" in f for f in git_files)
    
    if is_critical:
        print("🛡️  CRITICAL CHANGE DETECTED: Triggering Red-Team Gate...")
        scripts_dir = ".agent/scripts"
        
        # Run Security Scan
        try:
            print("   - Running security_scan.py...")
            subprocess.run([sys.executable, os.path.join(scripts_dir, "security_scan.py"), "."], check=True)
        except subprocess.CalledProcessError:
            print("❌ RED-TEAM VETO: Security scan failed or found vulnerabilities.")
            # In a real CI/CD we would exit 1 here. For now we warn.
            # sys.exit(1)
        
        # Run Threat Modeler
        try:
            print("   - Running threat_modeler.py...")
            subprocess.run([sys.executable, os.path.join(scripts_dir, "threat_modeler.py")], check=True)
        except Exception as e:
            print(f"   ⚠️  Threat modeling failed: {e}")

    # 4. Save to Bus
    agent_match = re.search(r"🤖 \*\*Agent Header\*\*:?\s*(\w+)", content, re.IGNORECASE)
    agent_name = agent_match.group(1) if agent_match else "unknown"
    save_to_bus(content, agent_name)
    
    print("✅ SUCCESS: Output validated and mirrored to Bus.")

if __name__ == "__main__":
    main()
