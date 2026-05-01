#!/usr/bin/env python3
"""Batch Runner — Dispatches parallel agent tasks from a JSON batch file.

Reads a JSON task batch, validates each task against known agents,
and generates orchestrator-compatible invocation summaries.

Usage:
    python3 batch_runner.py <batch_json_file>
    python3 batch_runner.py --generate --agents "frontend-specialist,backend-specialist" --task "Review auth"

Batch JSON format:
{
    "name": "Auth Review Batch",
    "tasks": [
        {"agent": "security-auditor", "instruction": "Audit auth flow", "priority": 1},
        {"agent": "test-engineer", "instruction": "Check test coverage for auth", "priority": 2}
    ]
}
"""
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / ".agent" / "agents"
BUS_FILE = REPO_ROOT / ".agent" / "bus" / "context.json"


def get_available_agents() -> set[str]:
    """Discover all available agent names from .agent/agents/."""
    if not AGENTS_DIR.exists():
        return set()
    return {f.stem for f in AGENTS_DIR.glob("*.md")}


def validate_batch(batch: dict) -> list[str]:
    """Validate a batch file structure and agent availability."""
    errors = []
    available = get_available_agents()

    if "tasks" not in batch:
        errors.append("Missing 'tasks' key in batch file")
        return errors

    tasks = batch["tasks"]
    if not isinstance(tasks, list) or len(tasks) == 0:
        errors.append("'tasks' must be a non-empty array")
        return errors

    for i, task in enumerate(tasks):
        if "agent" not in task:
            errors.append(f"Task [{i}]: missing 'agent' field")
        elif task["agent"] not in available:
            errors.append(f"Task [{i}]: unknown agent '{task['agent']}' (available: {', '.join(sorted(available)[:10])}...)")

        if "instruction" not in task:
            errors.append(f"Task [{i}]: missing 'instruction' field")

    return errors


def run_batch(batch_file: str) -> None:
    """Process a batch of tasks and output orchestration plan."""
    if not Path(batch_file).exists():
        print(f"❌ Batch file {batch_file} not found.")
        sys.exit(1)

    with open(batch_file, "r", encoding="utf-8") as f:
        batch = json.load(f)

    # Validate
    errors = validate_batch(batch)
    if errors:
        print("❌ Batch validation failed:")
        for err in errors:
            print(f"   • {err}")
        sys.exit(1)

    batch_name = batch.get("name", "Unnamed Batch")
    tasks = batch["tasks"]

    # Sort by priority if available
    tasks.sort(key=lambda t: t.get("priority", 99))

    # Analyze dependency structure
    independent = []
    sequential = []

    for task in tasks:
        if task.get("depends_on"):
            sequential.append(task)
        else:
            independent.append(task)

    print(f"🚀 Batch: {batch_name}")
    print(f"   Total tasks: {len(tasks)}")
    print(f"   Independent (parallelizable): {len(independent)}")
    print(f"   Sequential (has dependencies): {len(sequential)}")
    print()

    # Phase 1: Parallel tasks
    if independent:
        print("─── Phase 1: Parallel Dispatch ───")
        for task in independent:
            agent = task["agent"]
            instruction = task["instruction"]
            priority = task.get("priority", "—")
            print(f"  ⏳ [{priority}] {agent}: {instruction[:80]}")
        print()

    # Phase 2: Sequential tasks
    if sequential:
        print("─── Phase 2: Sequential Chain ───")
        for task in sequential:
            agent = task["agent"]
            instruction = task["instruction"]
            dep = task.get("depends_on", "?")
            print(f"  ⏳ {agent} (after {dep}): {instruction[:80]}")
        print()

    # Push batch context to bus
    _push_batch_to_bus(batch_name, tasks)

    print(f"✅ Batch dispatched. {len(tasks)} task(s) ready for orchestrator.")
    print(f"   Use: python3 .agent/scripts/bus_manager.py peek --limit {len(tasks)}")


def _push_batch_to_bus(batch_name: str, tasks: list) -> None:
    """Write batch plan to the Context Bus for orchestrator consumption."""
    bus = {"version": "1.0.0", "objects": []}
    if BUS_FILE.exists():
        try:
            with open(BUS_FILE, "r", encoding="utf-8") as f:
                bus = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    bus.setdefault("objects", []).append({
        "id": batch_id,
        "type": "requirement",
        "author": "batch_runner",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": {
            "batch_name": batch_name,
            "task_count": len(tasks),
            "tasks": [
                {"agent": t["agent"], "instruction": t["instruction"][:200]}
                for t in tasks
            ],
        },
    })

    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BUS_FILE, "w", encoding="utf-8") as f:
        json.dump(bus, f, indent=2, ensure_ascii=False)


def generate_batch(agents: str, task: str) -> None:
    """Generate a batch JSON template from agent list and task description."""
    agent_list = [a.strip() for a in agents.split(",")]
    available = get_available_agents()

    batch = {
        "name": f"Auto-generated: {task[:50]}",
        "tasks": [],
    }

    for i, agent in enumerate(agent_list):
        if agent not in available:
            print(f"⚠️  Warning: '{agent}' not found in agents directory")
        batch["tasks"].append({
            "agent": agent,
            "instruction": task,
            "priority": i + 1,
        })

    print(json.dumps(batch, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Batch Runner — Parallel Agent Task Dispatcher")
    parser.add_argument("batch_file", nargs="?", help="Path to batch JSON file")
    parser.add_argument("--generate", action="store_true", help="Generate a batch template")
    parser.add_argument("--agents", help="Comma-separated agent list (for --generate)")
    parser.add_argument("--task", help="Task description (for --generate)")

    args = parser.parse_args()

    if args.generate:
        if not args.agents or not args.task:
            print("❌ --generate requires --agents and --task")
            sys.exit(1)
        generate_batch(args.agents, args.task)
    elif args.batch_file:
        run_batch(args.batch_file)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
