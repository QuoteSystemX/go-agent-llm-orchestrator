#!/usr/bin/env python3
import os
import sys
import json
import uuid
import time
import shutil
import threading
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Setup imports
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

try:
    from lib.llm_client import query_llm_safe
except ImportError:
    # Fallback import if path setup has issues
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / "lib"))
    from llm_client import query_llm_safe

# Constants
TASKS_DIR = REPO_ROOT / "tasks"
RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"

# State Lock
state_lock = threading.Lock()

# Global config
rules = {}
agent_tiers = {}
ollama_models = {}

def load_router_rules():
    global rules, agent_tiers, ollama_models
    if not RULES_FILE.exists():
        return
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            rules = json.load(f)
        agent_tiers = rules.get("agent_tiers", {})
        ollama_models = rules.get("models", {}).get("ollama", {})
    except Exception as e:
        print(f"⚠️ Failed to load router rules: {e}")

def get_agent_concrete_model(agent_name: str, model_override: str = None) -> str:
    tier = model_override or agent_tiers.get(agent_name, "L2")
    return ollama_models.get(tier, "qwen2.5-coder:14b")

# YAML Frontmatter parser
def parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    
    idx = content.find("\n---", 3)
    if idx == -1:
        return {}, content
    
    fm_text = content[3:idx].strip()
    body = content[idx+4:].lstrip("\n")
    
    # Try importing PyYAML first
    try:
        import yaml
        data = yaml.safe_load(fm_text)
        if isinstance(data, dict):
            return data, body
    except ImportError:
        pass
    
    # Custom fallback YAML parser
    data = {}
    lines = fm_text.splitlines()
    current_key = None
    current_list = None
    current_dict_list = None
    current_dict = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
            
        indent = len(line) - len(line.lstrip())
        
        if stripped.startswith("-"):
            val = stripped[1:].strip()
            if ":" in val:
                # Key-value in a list item (dict list)
                k, _, v = val.partition(":")
                k = k.strip()
                v = v.strip().strip("'\"")
                if current_dict_list is not None:
                    current_dict = {k: v}
                    current_dict_list.append(current_dict)
            else:
                if current_list is not None:
                    current_list.append(val.strip("'\""))
            continue
            
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            
            if not val:
                current_key = key
                if key in ["validation"]:
                    current_dict_list = []
                    data[key] = current_dict_list
                    current_list = None
                else:
                    current_list = []
                    data[key] = current_list
                    current_dict_list = None
            else:
                if indent > 0 and current_dict is not None:
                    current_dict[key] = val
                else:
                    data[key] = val
                    current_key = None
                    current_list = None
                    current_dict_list = None
                    current_dict = None
                    
    return data, body

def serialize_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    # Dict item in list
                    first = True
                    for dk, dv in item.items():
                        if first:
                            lines.append(f"  - {dk}: {dv}")
                            first = False
                        else:
                            lines.append(f"    {dk}: {dv}")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"

class TaskNode:
    def __init__(self, file_path: Path, metadata: dict, body: str):
        self.file_path = file_path
        self.id = metadata.get("id", file_path.stem)
        self.agent = metadata.get("agent", "orchestrator")
        self.dependencies = metadata.get("dependencies") or []
        self.status = metadata.get("status", "pending")
        self.inputs = metadata.get("inputs") or []
        self.outputs = metadata.get("outputs") or []
        self.model_override = metadata.get("model_override")
        self.validation = metadata.get("validation") or []
        self.body = body
        self.metadata = metadata

    def save(self):
        self.metadata["status"] = self.status
        # Ensure outputs, inputs, dependencies, validation are kept in metadata
        self.metadata["id"] = self.id
        self.metadata["agent"] = self.agent
        self.metadata["dependencies"] = self.dependencies
        self.metadata["inputs"] = self.inputs
        self.metadata["outputs"] = self.outputs
        if self.model_override:
            self.metadata["model_override"] = self.model_override
        self.metadata["validation"] = self.validation

        fm_block = serialize_frontmatter(self.metadata)
        self.file_path.write_text(fm_block + self.body, encoding="utf-8")

def translate_path(p: str, run_dir: Path) -> Path:
    path_str = str(p).replace("\\", "/")
    if path_str.startswith(".agent/bus/artifacts/"):
        rel = path_str[len(".agent/bus/artifacts/"):]
        return run_dir / rel
    return REPO_ROOT / path_str

def detect_cycles(nodes: dict[str, TaskNode]) -> bool:
    visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited
    for node_id in nodes:
        visited[node_id] = 0

    def dfs(node_id):
        if visited[node_id] == 1:
            return True  # Cycle detected
        if visited[node_id] == 2:
            return False

        visited[node_id] = 1
        node = nodes[node_id]
        for dep in node.dependencies:
            if dep in nodes:
                if dfs(dep):
                    return True
        visited[node_id] = 2
        return False

    for node_id in nodes:
        if visited[node_id] == 0:
            if dfs(node_id):
                return True
    return False

def execute_task(node: TaskNode, run_dir: Path, active_models: set[str], model_name: str):
    print(f"🚀 [RUNNING] {node.id} using agent {node.agent} (Model: {model_name})")
    start_time = time.time()
    
    # 1. Capture initial output files timestamps
    initial_timestamps = {}
    for out in node.outputs:
        out_path = translate_path(out, run_dir)
        if out_path.exists():
            initial_timestamps[out] = out_path.stat().st_mtime
        else:
            initial_timestamps[out] = None

    # 2. Gather inputs content
    inputs_content = ""
    for inp in node.inputs:
        inp_path = translate_path(inp, run_dir)
        if not inp_path.exists():
            print(f"❌ [FAILED] {node.id}: Input file {inp} is missing.")
            with state_lock:
                node.status = "failed"
                node.save()
                active_models.remove(model_name)
            return
        
        # If it is an artifact on the bus, read it and add to inputs_content
        if str(inp).replace("\\", "/").startswith(".agent/bus/artifacts/"):
            try:
                content = inp_path.read_text(encoding="utf-8")
                inputs_content += f"\n### Artifact: {inp_path.name}\n```json\n{content}\n```\n"
            except Exception as e:
                print(f"⚠️ Failed to read input artifact {inp_path.name}: {e}")

    # 3. Load Agent instructions
    # Try finding agent md file recursively in .agent/agents/
    agent_file = None
    for root, _, files in os.walk(REPO_ROOT / ".agent" / "agents"):
        for f in files:
            if f.endswith(".md") and Path(f).stem == Path(node.agent).stem:
                agent_file = Path(root) / f
                break
        if agent_file:
            break

    if not agent_file:
        print(f"❌ [FAILED] {node.id}: Agent profile {node.agent} not found.")
        with state_lock:
            node.status = "failed"
            node.save()
            active_models.remove(model_name)
        return

    agent_fm, agent_sys_prompt = parse_yaml_frontmatter(agent_file.read_text(encoding="utf-8"))

    # 4. Construct prompt
    prompt = node.body
    if inputs_content:
        prompt = f"{prompt}\n\n## Входные артефакты от предыдущих шагов (Автоматический импорт):{inputs_content}"

    # 5. Query LLM via Broker
    tier = node.model_override or agent_fm.get("model", "L2")
    llm_response, source, stats = query_llm_safe(
        prompt=prompt,
        model=tier,
        system_prompt=agent_sys_prompt,
        default_model=model_name
    )

    # Auto-save LLM response to outputs if they don't exist yet (local non-tool execution fallback)
    if node.outputs and llm_response and source != "stub":
        extracted_content = llm_response.strip()
        if "```json" in extracted_content:
            try:
                parts = extracted_content.split("```json")
                if len(parts) > 1:
                    json_part = parts[1].split("```")[0].strip()
                    import json as json_lib
                    json_lib.loads(json_part)
                    extracted_content = json_part
            except Exception:
                pass
        elif extracted_content.startswith("```") and extracted_content.endswith("```"):
            lines = extracted_content.split("\n")
            if len(lines) > 2:
                extracted_content = "\n".join(lines[1:-1]).strip()

        # Write to the first output file by default
        first_out = translate_path(node.outputs[0], run_dir)
        if not first_out.exists():
            first_out.parent.mkdir(parents=True, exist_ok=True)
            first_out.write_text(extracted_content, encoding="utf-8")
            print(f"✍️ [AUTO-SAVED] {node.id} output written to: {node.outputs[0]}")

    # 6. Check output files modifications
    outputs_valid = True
    for out in node.outputs:
        out_path = translate_path(out, run_dir)
        # Ensure parent dirs exist
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not out_path.exists():
            outputs_valid = False
            err_msg = f"Output file {out} was not created."
            print(f"⚠️ [VALIDATION FAILED] {node.id}: {err_msg}")
            break
        else:
            prev_mtime = initial_timestamps.get(out)
            if prev_mtime is not None and out_path.stat().st_mtime <= prev_mtime:
                outputs_valid = False
                err_msg = f"Output file {out} was not modified by the agent."
                print(f"⚠️ [VALIDATION FAILED] {node.id}: {err_msg}")
                break

    # 7. Run validations
    validation_logs = []
    validation_success = outputs_valid

    if validation_success:
        for val_step in node.validation:
            step_name = val_step.get("name", "Unnamed Step")
            step_cmd = val_step.get("command", "")
            if not step_cmd:
                continue
                
            print(f"🧪 [VALIDATING] {node.id} -> Step: {step_name}")
            # Run command in project root
            res = subprocess.run(step_cmd, shell=True, cwd=str(REPO_ROOT), capture_output=True, text=True)
            log_entry = f"Step: {step_name}\nCommand: {step_cmd}\nExit Code: {res.returncode}\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}\n"
            validation_logs.append(log_entry)
            
            if res.returncode != 0:
                validation_success = False
                print(f"❌ [VALIDATION FAILED] {node.id} -> Step: {step_name} failed.")
                break

    duration = time.time() - start_time
    status = "completed" if validation_success else "failed"
    
    # 8. Save results and logs
    with state_lock:
        node.status = status
        
        # Append Execution Log
        log_text = f"\n## Результат выполнения\n{llm_response}\n\n## Лог выполнения\n"
        log_text += f"- **Status**: {status}\n"
        log_text += f"- **Run ID**: {run_dir.name}\n"
        log_text += f"- **Duration**: {duration:.2f}s\n"
        log_text += f"- **Model**: {stats.get('model', model_name)} (Source: {source})\n"
        
        if validation_logs:
            log_text += "\n### Validation Details:\n"
            log_text += "\n".join(validation_logs)
        else:
            if not outputs_valid:
                log_text += f"\n❌ Validation failed: Output files not modified/created.\n"
            else:
                log_text += "\n✓ No validation checks defined.\n"
                
        # Split body around original ## Результат выполнения or append
        res_idx = node.body.find("## Результат выполнения")
        if res_idx != -1:
            node.body = node.body[:res_idx] + log_text
        else:
            node.body = node.body + log_text
            
        node.save()
        active_models.remove(model_name)
        
    print(f"🏁 [FINISHED] {node.id} -> Status: {status.upper()} ({duration:.2f}s)")

def main():
    load_router_rules()
    
    # Parse tasks
    if not TASKS_DIR.exists():
        print(f"❌ Tasks directory missing at {TASKS_DIR}")
        sys.exit(1)
        
    nodes = {}
    for item in TASKS_DIR.glob("*.md"):
        # Skip directories
        if item.is_dir():
            continue
        try:
            fm, body = parse_yaml_frontmatter(item.read_text(encoding="utf-8"))
            if fm.get("id"):
                nodes[fm["id"]] = TaskNode(item, fm, body)
        except Exception as e:
            print(f"⚠️ Failed to parse task {item.name}: {e}")

    if not nodes:
        print("ℹ️ No task cards with valid Frontmatter IDs found in tasks/")
        sys.exit(0)

    # Validate graph (cycles)
    if detect_cycles(nodes):
        print("❌ [DEADLOCK] Cycle detected in tasks dependencies! Aborting DAG run.")
        sys.exit(1)

    # Setup Session
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_dir = REPO_ROOT / ".agent" / "bus" / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"📂 Created isolated artifact directory: {run_dir.relative_to(REPO_ROOT)}")

    # Concurrency Settings
    max_workers = int(os.environ.get("DAG_MAX_WORKERS", "3"))
    max_concurrent_models = int(os.environ.get("DAG_MAX_CONCURRENT_MODELS", "1"))
    
    active_models = set()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    
    print(f"⚙️ Concurrency: max_workers={max_workers}, max_concurrent_models={max_concurrent_models}")

    dag_failed = False
    
    # Main loop
    while True:
        with state_lock:
            # Check overall status
            all_completed = True
            any_running = False
            pending_nodes = []
            
            for node in nodes.values():
                if node.status == "failed":
                    dag_failed = True
                elif node.status == "running":
                    any_running = True
                elif node.status == "pending":
                    all_completed = False
                    pending_nodes.append(node)
                    
            if dag_failed:
                break
                
            if all_completed and not any_running:
                break
                
            # Find eligible nodes
            eligible_nodes = []
            for node in pending_nodes:
                deps_ok = True
                for dep in node.dependencies:
                    dep_node = nodes.get(dep)
                    if not dep_node or dep_node.status != "completed":
                        deps_ok = False
                        break
                if deps_ok:
                    eligible_nodes.append(node)

            # Submit tasks matching Model Concurrency Guard
            for node in eligible_nodes:
                m_name = get_agent_concrete_model(node.agent, node.model_override)
                
                # Check if model is already active OR we have room for a new model
                can_run = False
                if m_name in active_models:
                    can_run = True
                elif len(active_models) < max_concurrent_models:
                    can_run = True
                    
                if can_run:
                    node.status = "running"
                    node.save()
                    active_models.add(m_name)
                    executor.submit(execute_task, node, run_dir, active_models, m_name)
                    any_running = True
            
            # Deadlock check: no running tasks and no eligible tasks can run
            if not any_running and pending_nodes:
                # Check if all pending nodes are blocked by model concurrency or failed parents
                has_pending_valid = False
                for node in pending_nodes:
                    deps_failed = False
                    for dep in node.dependencies:
                        dep_node = nodes.get(dep)
                        if dep_node and dep_node.status == "failed":
                            deps_failed = True
                            break
                    if not deps_failed:
                        has_pending_valid = True
                        
                if not has_pending_valid:
                    print("❌ [DEADLOCK] Remaining tasks blocked by failed dependencies.")
                    dag_failed = True
                    break
                else:
                    # Model concurrency block — wait for running tasks to finish
                    pass

        time.sleep(0.5)

    # Cleanup or preserve
    if dag_failed:
        print(f"❌ [DAG FAILED] One or more tasks failed. Artifacts preserved in: {run_dir.relative_to(REPO_ROOT)}")
        sys.exit(1)
    else:
        print("✅ [DAG SUCCESS] All tasks executed successfully!")
        try:
            shutil.rmtree(run_dir)
            print("🧹 Cleaned up isolated artifact directory.")
        except Exception as e:
            print(f"⚠️ Failed to delete run directory: {e}")
        sys.exit(0)

if __name__ == "__main__":
    main()
