#!/usr/bin/env python3
"""Ollama Agent Wrapper - Execute subagents with Ollama models and filesystem tools.

Usage:
    python3 ollama_agent.py "task description" --agent code-archaeologist
    python3 ollama_agent.py "find technical debt" --agent reviewer
    python3 ollama_agent.py "analyze codebase"  # Auto-select best model
"""

import sys
from pathlib import Path
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

import json
import subprocess
import time
import urllib.request
from datetime import datetime

from lib.common import discover_ollama_url
OLLAMA_URL = discover_ollama_url()

# Benchmark-optimized model assignments
MODEL_MAP = {
    "L1": "codestral:22b",
    "L2": "qwen2.5-coder:14b",
    "L3": "qwen2.5-coder:32b",
    "L4": "qwen3-coder:30b",
}

# Speed ranking (lower = faster)
MODEL_RANKING = [
    ("qwen3-coder:30b", 3.6, 129),   # BEST L4 - 3.6s, 129 tps
    ("qwen2.5-coder:14b", 6.4, 61),   # BEST L2 - 6.4s, 61 tps
    ("codestral:22b", 7.4, 39),       # BEST L1 - 7.4s, 39 tps
    ("qwen2.5-coder:32b", 13.6, 28), # L3 - 13.6s, 28 tps
    ("qwen3:32b", 29.3, 15),          # L4-alt - 29.3s, 15 tps
    ("qwen3.6:27b", 53.8, 8),         # L4-alt - 53.8s, 8 tps
]


def is_wsl() -> bool:
    """Detect if running inside WSL."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False


def get_best_model(task_complexity: int = 5) -> str:
    """Auto-select best model based on task complexity (1-10)."""
    if task_complexity <= 3:
        return MODEL_MAP["L1"]
    elif task_complexity <= 6:
        return MODEL_MAP["L2"]
    elif task_complexity <= 9:
        return MODEL_MAP["L3"]
    else:
        return MODEL_MAP["L4"]


def query_ollama(prompt: str, model: str = "qwen3-coder:30b") -> tuple[str, float, float]:
    """Send prompt to Ollama and get response with timing."""
    req_data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 8192}
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(req_data).encode(),
        headers={"Content-Type": "application/json"}
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
            elapsed = time.time() - start
            tokens = len(result.get("response", "")) // 4
            tps = tokens / elapsed if elapsed > 0 else 0
            return result.get("response", ""), elapsed, tps
    except Exception as e:
        return f"❌ Ollama error: {e}", time.time() - start, 0


def read_file(path: str) -> str:
    """Read file contents."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()[:10000]  # Limit to 10k chars
    except Exception as e:
        return f"❌ Error reading {path}: {e}"


def grep_files(pattern: str, path: str = ".") -> str:
    """Grep for pattern in files."""
    try:
        result = subprocess.run(
            ["grep", "-rn", pattern, path, "--include=*.py", "--include=*.md"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout[:5000] if result.stdout else "No matches"
    except Exception as e:
        return f"❌ Grep error: {e}"


def list_dir(path: str) -> str:
    """List directory contents."""
    try:
        result = subprocess.run(
            ["ls", "-la", path],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"❌ ls error: {e}"


def get_agent_prompt(agent: str, task: str) -> str:
    """Generate prompt for agent with context."""
    
    base_prompt = f"""You are executing a task as {agent} agent.
Your job: {task}

IMPORTANT: 
1. You have access to these tools: read_file(), grep_files(), list_dir()
2. Use them to gather data about the codebase
3. Then send your analysis to Ollama for deep reasoning
4. Combine tool results + Ollama analysis into final report

WORKFLOW:
1. Use list_dir(), grep_files(), read_file() to gather data
2. Send findings to Ollama: query_ollama("analyze this data: <data>")
3. Synthesize results and provide actionable output

Project: {REPO_ROOT}

Start by gathering context data."""
    
    agent_prompts = {
        "code-archaeologist": """You are code-archaeologist.
Search for: dead code, duplicate logic, missing tests, TODO/FIXME markers.
Use grep_files("TODO\\|FIXME") to find markers.
Use list_dir(".agent/scripts") to map scripts.""",
        
        "reviewer": """You are reviewer agent.
Scan for: pattern inconsistencies, import issues, config conflicts.
Check .agent/config/ for config drift.""",
        
        "wiki-architect": """You are wiki-architect agent.
Analyze documentation drift, broken links, stale docs.
Check docs/, wiki/ directories.""",
        
        "explorer-agent": """You are explorer-agent agent.
Map directory structure, find orphaned files, naming violations.""",
        
        "general": """You are a general-purpose analysis agent.
Perform thorough analysis based on task requirements.
Use all available tools."""
    }
    
    return base_prompt + "\n\n" + agent_prompts.get(agent, agent_prompts["general"])


def execute_with_ollama(task: str, agent: str = "general", model: str = None) -> str:
    """Execute task using Ollama with tool results."""
    
    # Auto-select best model if not specified
    if model is None:
        # Infer complexity from task keywords
        complexity_keywords = {
            "analyze": 7, "audit": 8, "architecture": 9, "refactor": 6,
            "find": 3, "list": 2, "check": 3, "verify": 4,
            "implement": 6, "create": 5, "fix": 4, "review": 5
        }
        complexity = 5  # default
        for keyword, score in complexity_keywords.items():
            if keyword in task.lower():
                complexity = max(complexity, score)
        model = get_best_model(complexity)
    
    print(f"🤖 Flow: [L{'4' if 'analyze' in task.lower() or 'audit' in task.lower() else '2'}] → Ollama Agent")
    print(f"🧠 Provider: Ollama (WSL auto-detected)")
    print(f"🧠 Model: {model}")
    print()
    
    # Get agent prompt
    prompt = get_agent_prompt(agent, task)
    
    # Step 1: Gather data using subprocess
    print("📂 Gathering context data...")
    
    data_gathered = {
        "scripts_count": list_dir(str(REPO_ROOT / ".agent" / "scripts")),
        "skills_count": list_dir(str(REPO_ROOT / ".agent" / "skills")),
        "todo_fixes": grep_files("TODO\\|FIXME", str(REPO_ROOT / ".agent" / "scripts")),
    }
    
    # Step 2: Send to Ollama for analysis
    print(f"🧠 Sending to Ollama ({model})...")
    context_for_ollama = f"""
TASK: {task}
AGENT: {agent}

CONTEXT DATA:
- Scripts: {data_gathered['scripts_count'][:500]}
- TODO/FIXME: {data_gathered['todo_fixes'][:1000]}

Analyze this data and provide:
1. Key findings
2. Specific file paths with issues
3. Recommended fixes
4. Priority (HIGH/MEDIUM/LOW)
"""
    
    start = datetime.now()
    result, elapsed, tps = query_ollama(context_for_ollama, model)
    
    print(f"⏱ Ollama time: {elapsed:.1f}s | {tps:.0f} tok/s")
    print()
    print("="*60)
    print("📥 OLLAMA ANALYSIS RESULT:")
    print("="*60)
    print(result)
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Execute task via Ollama agent")
    parser.add_argument("task", help="Task description")
    parser.add_argument("--agent", default="general", help="Agent type (code-archaeologist, reviewer, etc)")
    parser.add_argument("--model", help="Ollama model (auto-selected if not specified)")
    parser.add_argument("--auto", action="store_true", help="Auto-select best model")
    
    args = parser.parse_args()
    
    print(f"🧠 WSL Detected: {is_wsl()}")
    print(f"🧠 Ollama URL: {OLLAMA_URL}")
    print()
    
    # Auto model selection
    model = args.model
    if args.auto or not model:
        complexity_keywords = {
            "analyze": 8, "audit": 9, "architecture": 10, "refactor": 7,
            "find": 3, "list": 2, "check": 4, "verify": 5,
            "implement": 6, "create": 5, "fix": 4, "review": 5
        }
        complexity = 5
        for keyword, score in complexity_keywords.items():
            if keyword.lower() in args.task.lower():
                complexity = max(complexity, score)
        model = get_best_model(complexity)
        print(f"🎯 Auto-selected model: {model} (complexity: {complexity})")
    else:
        print(f"🎯 Using specified model: {model}")
    
    result = execute_with_ollama(args.task, args.agent, model)
    
    # Push to bus
    push_to_telemetry(args.task, args.agent, model, result)


def push_to_telemetry(task: str, agent: str, model: str, result: str):
    """Push result to telemetry bus."""
    try:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
        from lib.paths import TELEMETRY_PATH
        from lib.common import load_json_safe, save_json_atomic
        
        telemetry = load_json_safe(TELEMETRY_PATH)
        if "ollama_agent_results" not in telemetry:
            telemetry["ollama_agent_results"] = []
        
        telemetry["ollama_agent_results"].append({
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "agent": agent,
            "model": model,
            "result_preview": result[:500]
        })
        
        save_json_atomic(TELEMETRY_PATH, telemetry)
        print()
        print("✅ Result pushed to telemetry")
    except Exception as e:
        print(f"⚠️ Bus push failed: {e}")


if __name__ == "__main__":
    main()
