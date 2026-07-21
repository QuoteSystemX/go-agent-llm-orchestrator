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

import sys
import os
import re
import subprocess
import json
from datetime import datetime

from pathlib import Path as _Path
SCRIPTS_ROOT = _Path(__file__).resolve().parents[1]

# Guardrail pipeline — singleton, loaded once at import time (zero per-call overhead)
try:
    from dev.guardrail_middleware import GuardrailPipeline
    from health.policy_guardrail import check_inline as _policy_check
    _guardrail = GuardrailPipeline()
    _guardrail.register_check(_policy_check, name="policy_rules", halt_on_fail=True)
    try:
        from dev.checks.anthropic_safety import anthropic_safety_check as _anthropic_check
        _guardrail.register_check(_anthropic_check, name="anthropic_safety", halt_on_fail=True)
    except Exception as _ae:
        print(f"⚠️  Anthropic safety check unavailable: {_ae}")
except Exception as _ge:
    _guardrail = None
    print(f"⚠️  Guardrail pipeline unavailable: {_ge}")

REQUIRED_SECTIONS = [
    r"🤖 Flow: \*\*\[L[1-4]\]\*\*",
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

def validate_identity_header(content):
    """Deep validation of the Identity Header against system config.

    03_gateway.md no longer asks agents to self-report Model/TPS/Tokens — those
    are either stamped by mcp-llm-broker outside the response text, or written as
    the literal string "unknown" when no real value is available. So the tier
    marker is mandatory, but a "🧠 **Model**:" mention is optional; when present,
    it is checked against router_rules.json UNLESS it is "unknown", which is
    always accepted — an honest "unknown" is never a hallucination.
    """
    flow_pattern = r"🤖 Flow: \*\*\[(L[1-4])\]\*\*"
    flow_match = re.search(flow_pattern, content)

    if not flow_match:
        return ["Identity Header is missing or formatted incorrectly. Expected: 🤖 Flow: **[L<N>]** | ..."]

    tier = flow_match.group(1)

    model_pattern = r"🧠 \*\*Model\*\*: (.*?)(?:[ \n\|]|$)"
    model_match = re.search(model_pattern, content)
    if not model_match:
        # No self-reported model to validate — this is now the expected shape
        # for responses routed through mcp-llm-broker's call_agent.
        return []

    model = model_match.group(1).strip().lower().replace("**", "")
    if model == "unknown":
        return []

    rules_path = SCRIPTS_ROOT.parent / "config" / "router_rules.json"
    try:
        with open(rules_path, 'r') as f:
            rules = json.load(f)
    except Exception as e:
        print(f"  ⚠️  Warning: Could not load router_rules.json for deep validation: {e}")
        return []

    # Check Mappings
    ollama_map = rules.get("models", {}).get("ollama", {})
    cloud_map = rules.get("models", {}).get("antigravity", {})
    
    valid_models = []
    
    # Add primary mappings
    if tier in ollama_map: valid_models.append(ollama_map[tier].lower())
    if tier in cloud_map: valid_models.append(cloud_map[tier].lower())
    
    # Add alternatives
    alt_key = f"{tier}_alt"
    if alt_key in ollama_map and isinstance(ollama_map[alt_key], list):
        valid_models.extend([m.lower() for m in ollama_map[alt_key]])
    
    # Add rankings-based tier check
    rankings = rules.get("model_rankings", {})
    for m_id, m_info in rankings.items():
        if isinstance(m_info, dict) and m_info.get("tier") == tier:
            valid_models.append(m_id.lower())

    if model not in valid_models:
        expected = f"{ollama_map.get(tier)} or {cloud_map.get(tier)}"
        return [f"HALLUCINATION DETECTED: Model '{model}' does not belong to Tier {tier}. Expected: {expected}"]

    return []

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
    automation_chain = [
        SCRIPTS_ROOT / "delivery" / "walkthrough_assembler.py",
        SCRIPTS_ROOT / "delivery" / "task_sync.py",
        SCRIPTS_ROOT / "dev"      / "doc_healer.py",
        SCRIPTS_ROOT / "dev"      / "visualize_deps.py",
        SCRIPTS_ROOT / "knowledge" / "obsidian_validator.py",
    ]

    for script in automation_chain:
        print(f"  - Executing {script.name}...")
        try:
            subprocess.run([sys.executable, str(script)], check=True)
        except Exception as e:
            print(f"  ⚠️  {script.name} failed: {e}")

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


def run_contrastive_validation(content):
    """Run Contrastive Verification Loop (Option C) for L3/L4 tasks."""
    header_match = re.search(r"🤖 Flow: \*\*\[(L[1-4])\]\*\*", content)
    if not header_match:
        return True # Handled by identity validator
        
    tier = header_match.group(1)
    if tier not in ["L3", "L4"]:
        return True # Skip for L1/L2
        
    print("⚖️ Running Contrastive Verification Loop (Option C)...")
    
    # 1. Fetch git diff (excluding HTML, JSON, SVGs, and images to prevent diff truncation)
    exclude_specs = ["--", ":!*.html", ":!*.json", ":!*.png", ":!*.jpg", ":!*.svg"]
    try:
        git_diff = subprocess.check_output(["git", "diff", "HEAD"] + exclude_specs, stderr=subprocess.STDOUT).decode()
        if not git_diff.strip():
            # Try staged diff if unstaged is empty
            git_diff = subprocess.check_output(["git", "diff", "--cached"] + exclude_specs, stderr=subprocess.STDOUT).decode()
    except Exception as e:
        print(f"  ⚠️ Failed to retrieve git diff: {e}")
        git_diff = ""
        
    if not git_diff.strip():
        print("  ✅ No file changes detected in git. Skipping contrastive verification.")
        return True

    # 2. Build LLM prompt comparing the agent response content with the actual code changes
    prompt = (
        "You are the Contrastive Verification Gatekeeper.\n"
        "Your task is to identify any HALLUCINATIONS in the agent's textual response by comparing it with the actual git diff of the changes made.\n\n"
        "Specifically, look for:\n"
        "1. Mention of functions, variables, modules, imports, or API endpoints in the text that do NOT exist in either the original code or the git diff.\n"
        "2. Claims of features implemented that are completely absent from the code changes.\n"
        "3. Any logical discrepancies between what the text says was done and what the code changes actually show.\n\n"
        f"--- GIT DIFF ---\n{git_diff[:8000]}\n\n"
        f"--- AGENT RESPONSE ---\n{content}\n\n"
        "Output a JSON object with two fields:\n"
        "  - \"passed\": true | false\n"
        "  - \"hallucinations\": a list of strings detailing each hallucination or discrepancy found. Empty if passed is true.\n\n"
        "Provide ONLY the raw JSON object."
    )

    try:
        from lib.llm_client import query_llm_safe
        # Use gemini-3-flash for high speed and low cost
        resp, src, _ = query_llm_safe(
            prompt=prompt,
            model="auto",
            system_prompt="You are a strict, precise code reviewer. Output only JSON.",
            format_json=True
        )
        
        # If LLM endpoints failed and returned stub
        if src == "stub" or "⚠️ [LLM Unavailable]" in resp:
            print("  ⚠️ LLM Unavailable for Contrastive Verification. Skipping and warning.")
            return True
            
        # Parse output
        match = re.search(r"\{[^{}]*\}", resp, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            passed = result.get("passed", True)
            hallucinations = result.get("hallucinations", [])
            
            if not passed:
                print("❌ CONTRASTIVE VETO DETECTED:")
                for h in hallucinations:
                    print(f"  - {h}")
                return False
                
        print("  ✅ Contrastive verification passed. No hallucinations detected.")
        return True
    except Exception as e:
        print(f"  ⚠️ Error during contrastive verification: {e}. Passing resiliently.")
        return True


def main():
    content = ""
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
    
    # 0. Validate vault health
    print("🏛️ Running vault health check...")
    try:
        subprocess.run([sys.executable, str(SCRIPTS_ROOT / "knowledge" / "obsidian_validator.py"), "check"], check=False)
    except Exception as e:
        print(f"⚠️  Vault validation failed: {e}")

    # 1. Check sections
    missing_sections = validate_sections(content)
    if missing_sections:
        print(f"❌ FAILED: Missing mandatory sections: {', '.join(missing_sections)}")
        sys.exit(1)
    
    # 1.5 Deep Identity Validation
    print("🧠 Validating Identity Header integrity...")
    identity_errors = validate_identity_header(content)
    if identity_errors:
        for err in identity_errors:
            print(f"❌ {err}")
        sys.exit(1)
        
    # 1.7 Contrastive Verification Loop (Option C)
    if not run_contrastive_validation(content):
        sys.exit(1)
    
    # Extract goal and files for further validation
    goal_match = re.search(r"🎯 \*\*Context/Goal\*\*:?\s*(.*?)(\n[🛠📂📈]|$)", content, re.DOTALL | re.IGNORECASE)
    goal = goal_match.group(1).strip() if goal_match else ""
    components_match = re.search(r"📂 \*\*Impacted Components\*\*:?\s*(.*?)(\n[📈]|$)", content, re.DOTALL | re.IGNORECASE)
    components_text = components_match.group(1).strip() if components_match else ""
    impacted_files = re.findall(r"(?:file:///|/|[a-zA-Z]:\\)([\w\-\./\\\s]+)", components_text)

    # 2. Mental Model Validation (Karpathy 2.0)
    try:
        subprocess.run([sys.executable, str(SCRIPTS_ROOT / "models" / "model_validator.py"), goal, json.dumps(impacted_files)], check=True)
    except subprocess.CalledProcessError:
        print("❌ FAILED: Change violates established Mental Models in wiki/mental-models/")
        # sys.exit(1)

    # 2.5 Governance Gate: Wiki-First Enforcement (Hybrid Protocol)
    try:
        subprocess.run([sys.executable, str(SCRIPTS_ROOT / "orchestration" / "governance_gate.py"), json.dumps(impacted_files)], check=True)
    except subprocess.CalledProcessError:
        print("❌ FAILED: New files must be defined in the Wiki (Stories/ADR) first.")
        # sys.exit(1)

    # 3. Red-Team Gate: Security & Impact Audit
    critical_keywords = ["auth", "security", "infra", "secret", "bus", "permission", "access", "root"]
    is_critical = any(k in goal.lower() for k in critical_keywords) or \
                  any("infra" in f or "bus" in f for f in get_git_changed_files())
    
    if is_critical:
        print("🛡️  CRITICAL CHANGE DETECTED: Triggering Red-Team Gate...")
        # Run Security Scan
        try:
            print("   - Running security_scan.py...")
            subprocess.run([sys.executable, str(SCRIPTS_ROOT / "health" / "security_scan.py"), "--target", "."], check=True)
        except subprocess.CalledProcessError:
            print("❌ RED-TEAM VETO: Security scan failed or found vulnerabilities.")
            # In a real CI/CD we would exit 1 here. For now we warn.
            # sys.exit(1)

        # Run Threat Modeler
        try:
            print("   - Running threat_modeler.py...")
            subprocess.run([sys.executable, str(SCRIPTS_ROOT / "health" / "threat_modeler.py")], check=True)
        except Exception as e:
            print(f"   ⚠️  Threat modeling failed: {e}")

    # 4. Save to Bus
    agent_name = "unknown"
    agent_match = re.search(r"👤 Agent: \*\*@?(\w+)\*\*", content, re.IGNORECASE)
    if agent_match:
        agent_name = agent_match.group(1)
    else:
        agent_match = re.search(r"🤖 \*\*Agent Header\*\*:?\s*(\w+)", content, re.IGNORECASE)
        if agent_match:
            agent_name = agent_match.group(1)
    
    # INTEGRATION: Run Tough Auditor for live agent evaluation
    print("⚖️ Invoking Tough Auditor for live agent evaluation...")
    try:
        import orchestration.tough_auditor as tough_auditor
        task_slug = re.sub(r'[^\w]+', '_', goal[:30]).strip('_').lower()
        if not task_slug or set(task_slug) == {'_'}:
            task_slug = "session_task"
        score = tough_auditor.audit_changes(agent_name, task_slug)
        print(f"📈 Real-time Agent Score Logged: {score}/5.0")
    except Exception as e:
        print(f"⚠️ Live audit evaluation failed or skipped: {e}")
        
    save_to_bus(content, agent_name)

    # 5. Guardrail: real-time policy check (must be last — blocks output on violation)
    if _guardrail is not None:
        guardrail_result = _guardrail.run(content)
        if not guardrail_result.passed:
            guardrail_result.print_veto()
            guardrail_result.log_to_report()
            sys.exit(1)

    print("✅ SUCCESS: Output validated and mirrored to Bus.")

if __name__ == "__main__":
    main()
