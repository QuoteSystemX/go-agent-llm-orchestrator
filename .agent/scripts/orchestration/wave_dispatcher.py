
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
import json
import subprocess
from pathlib import Path

def parse_mermaid_dag(plan_content):
    """
    Simplified Mermaid DAG parser for extracting nodes and dependencies.
    Looks for patterns like A --> B or A[Label] --> B[Label].
    """
    edges = []
    nodes = {}
    
    # Regex for edges: ID1[Label] --> ID2[Label]
    # Or simply ID1 --> ID2
    pattern = r"(\w+)(?:\[.*?\])?\s*-->\s*(\w+)(?:\[.*?\])?"
    
    matches = re.findall(pattern, plan_content)
    for src, dst in matches:
        edges.append((src, dst))
        if src not in nodes: nodes[src] = []
        if dst not in nodes: nodes[dst] = []
        
    return nodes, edges

def get_execution_waves(nodes, edges):
    """
    Topological sort algorithm to divide into waves.
    """
    in_degree = {node: 0 for node in nodes}
    for src, dst in edges:
        in_degree[dst] += 1
        
    waves = []
    while True:
        current_wave = [node for node, degree in in_degree.items() if degree == 0]
        if not current_wave:
            break
        
        waves.append(current_wave)
        for node in current_wave:
            # "Remove" node and decrease in-degree of dependent nodes
            for src, dst in edges:
                if src == node:
                    in_degree[dst] -= 1
            del in_degree[node]
            
    return waves

def check_ready_nodes(nodes, edges, session_state):
    """
    Finds nodes whose dependencies are fully completed.
    """
    ready_nodes = []
    completed_tasks = [k.replace("task_", "") for k, v in session_state.items() if v == "completed"]
    
    # Nodes that haven't started yet
    pending_nodes = [node for node in nodes if f"task_{node}" not in session_state or session_state[f"task_{node}"] == "pending"]
    
    for node in pending_nodes:
        # Look for all incoming edges for this node
        dependencies = [src for src, dst in edges if dst == node]
        if all(dep in completed_tasks for dep in dependencies):
            ready_nodes.append(node)
            
    return ready_nodes

def execute_node(session_id, node, description=""):
    """
    Node execution. Supports recursive calls.
    """
    print(f"🚀 Executing Node: {node}")
    
    # Recursion check
    if "[RECURSIVE]" in description:
        print(f"  📂 Detected Recursive Task. Spawning sub-session...")
        sub_sid_proc = subprocess.run(
            ["python3", ".agent/scripts/orchestration/orchestration_session.py", "init"],
            capture_output=True, text=True
        )
        sub_sid = sub_sid_proc.stdout.strip()
        subprocess.run([
            "python3", ".agent/scripts/orchestration/orchestration_session.py", 
            "set-state", session_id, f"subsession_{node}", sub_sid
        ])
        print(f"  ✅ Sub-session created: {sub_sid}")

    # Update status
    subprocess.run([
        "python3", ".agent/scripts/orchestration/orchestration_session.py", 
        "set-state", session_id, f"task_{node}", "completed"
    ])
    print(f"  🏁 Node {node} completed.")

def run_jit_dispatcher(session_id, nodes, edges, descriptions):
    """
    Main JIT dispatcher loop.
    """
    print("🌊 Starting JIT Dispatcher...")
    
    # Initialize all nodes as pending
    for node in nodes:
        subprocess.run([
            "python3", ".agent/scripts/orchestration/orchestration_session.py", 
            "set-state", session_id, f"task_{node}", "pending"
        ])

    while True:
        # Read current state
        state_proc = subprocess.run(
            ["python3", ".agent/scripts/orchestration/orchestration_session.py", "get-state", session_id],
            capture_output=True, text=True
        )
        try:
            session_state = json.loads(state_proc.stdout)
        except json.JSONDecodeError:
            break

        ready_nodes = check_ready_nodes(nodes, edges, session_state)
        
        if not ready_nodes:
            # Check if there are tasks currently running
            running = [k for k, v in session_state.items() if v == "running"]
            pending = [k for k, v in session_state.items() if v == "pending"]
            
            if not running and not pending:
                break
                
            # If running or pending tasks exist — wait for signal (simulation)
            import time
            time.sleep(2) 
            continue
            
        for node in ready_nodes:
            execute_node(session_id, node, descriptions.get(node, ""))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: wave_dispatcher.py <session_id> <plan_file>")
        sys.exit(1)
        
    session_id = sys.argv[1]
    plan_file = Path(sys.argv[2])
    
    with open(plan_file, "r") as f:
        content = f.read()
        
    nodes, edges = parse_mermaid_dag(content)
    
    # Extract descriptions from Mermaid (more robust regex)
    descriptions = {}
    # Search for ID[Label] or ID(Label) or ID((Label))
    desc_patterns = [
        r"(\w+)\[(.*?)\]",
        r"(\w+)\((.*?)\)",
        r"(\w+)\{\{(.*?)\}\}"
    ]
    for pattern in desc_patterns:
        for node_id, label in re.findall(pattern, content):
            descriptions[node_id] = label

    run_jit_dispatcher(session_id, nodes, edges, descriptions)
    print("✅ Dispatcher finished.")
