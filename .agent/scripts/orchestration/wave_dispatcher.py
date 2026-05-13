
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
    Упрощенный парсер Mermaid DAG для извлечения узлов и зависимостей.
    Ищет паттерны типа A --> B или A[Label] --> B[Label].
    """
    edges = []
    nodes = {}
    
    # Регулярное выражение для ребер: ID1[Label] --> ID2[Label]
    # Или просто ID1 --> ID2
    pattern = r"(\w+)(?:\[.*?\])?\s*-->\s*(\w+)(?:\[.*?\])?"
    
    matches = re.findall(pattern, plan_content)
    for src, dst in matches:
        edges.append((src, dst))
        if src not in nodes: nodes[src] = []
        if dst not in nodes: nodes[dst] = []
        
    return nodes, edges

def get_execution_waves(nodes, edges):
    """
    Алгоритм топологической сортировки для разделения на волны.
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
            # "Удаляем" узел и уменьшаем степень вхождения зависимых узлов
            for src, dst in edges:
                if src == node:
                    in_degree[dst] -= 1
            del in_degree[node]
            
    return waves

def check_ready_nodes(nodes, edges, session_state):
    """
    Находит узлы, чьи зависимости полностью выполнены (completed).
    """
    ready_nodes = []
    completed_tasks = [k.replace("task_", "") for k, v in session_state.items() if v == "completed"]
    
    # Узлы, которые еще не запускались
    pending_nodes = [node for node in nodes if f"task_{node}" not in session_state or session_state[f"task_{node}"] == "pending"]
    
    for node in pending_nodes:
        # Ищем все входящие ребра для этого узла
        dependencies = [src for src, dst in edges if dst == node]
        if all(dep in completed_tasks for dep in dependencies):
            ready_nodes.append(node)
            
    return ready_nodes

def execute_node(session_id, node, description=""):
    """
    Запуск узла. Поддерживает рекурсивный вызов.
    """
    print(f"🚀 Executing Node: {node}")
    
    # Проверка на рекурсию
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

    # Обновляем статус
    subprocess.run([
        "python3", ".agent/scripts/orchestration/orchestration_session.py", 
        "set-state", session_id, f"task_{node}", "completed"
    ])
    print(f"  🏁 Node {node} completed.")

def run_jit_dispatcher(session_id, nodes, edges, descriptions):
    """
    Основной цикл JIT-диспетчера.
    """
    print("🌊 Starting JIT Dispatcher...")
    
    # Инициализируем все узлы как pending
    for node in nodes:
        subprocess.run([
            "python3", ".agent/scripts/orchestration/orchestration_session.py", 
            "set-state", session_id, f"task_{node}", "pending"
        ])

    while True:
        # Читаем текущее состояние
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
            # Проверяем, есть ли задачи, которые сейчас выполняются
            running = [k for k, v in session_state.items() if v == "running"]
            pending = [k for k, v in session_state.items() if v == "pending"]
            
            if not running and not pending:
                break
                
            # Если есть запущенные или ожидающие — ждем сигнала (имитация)
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
    
    # Извлечение описаний из Mermaid (более надежное регулярное выражение)
    descriptions = {}
    # Ищем ID[Label] или ID(Label) или ID((Label))
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
