#!/usr/bin/env python3
"""
Chaos Monkey - Resilience Testing & Failure Injection
Intentionally injects failures into the orchestration pipeline to test stability.
"""

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
import json
import random
import time
import subprocess
from pathlib import Path

# Safety Switch
CHAOS_ENABLED = os.environ.get("CHAOS_ENABLED") == "1"

REPO_ROOT = Path(__file__).resolve().parents[3]
BUS_DIR = REPO_ROOT / ".agent" / "bus"

def kill_mcp():
    print("🔥 Chaos Monkey: Killing MCP Server...")
    # Find process by name patterns
    patterns = ["local-skill-server", "agent-kit-server"]
    for p in patterns:
        subprocess.run(["pkill", "-f", p], capture_output=True)
    return True

def corrupt_bus():
    print("🦠 Chaos Monkey: Corrupting Context Bus...")
    files = list(BUS_DIR.glob("*.json"))
    if not files:
        print("   No files to corrupt.")
        return False
    
    target = random.choice(files)
    try:
        content = target.read_text()
        # Inject invalid JSON (e.g., remove a closing brace)
        if len(content) > 5:
            corrupted = content[:-2] 
            target.write_text(corrupted)
            print(f"   Corrupted: {target.name}")
            return True
        return False
    except Exception as e:
        print(f"   Failed to corrupt: {e}")
        return False

def inject_latency():
    print("⏳ Chaos Monkey: Injecting Latency (5s)...")
    time.sleep(5)
    return True

def cpu_spike(duration=10):
    print(f"🔥 Chaos Monkey: Spiking CPU for {duration}s...")
    # Simple busy loop to consume CPU
    end = time.time() + duration
    while time.time() < end:
        _ = [x**2 for x in range(1000)]
    return True

def memory_leak(mb=512):
    print(f"🔥 Chaos Monkey: Simulating {mb}MB Memory Leak...")
    # Allocate a large list to consume memory
    _ = [0] * (mb * 1024 * 1024 // 8) 
    time.sleep(5)
    return True

def main() -> None:
    if not CHAOS_ENABLED:
        print("❌ CHAOS DISABLED. Set CHAOS_ENABLED=1 to run.")
        sys.exit(0)

    import argparse
    parser = argparse.ArgumentParser(description="Chaos Monkey Failure Injector")
    parser.add_argument("--kill-mcp", action="store_true", help="Kill the MCP server")
    parser.add_argument("--corrupt-bus", action="store_true", help="Corrupt a random bus file")
    parser.add_argument("--latency", action="store_true", help="Inject 5s latency")
    parser.add_argument("--cpu", action="store_true", help="Spike CPU")
    parser.add_argument("--memory", action="store_true", help="Simulate Memory Leak")
    parser.add_argument("--analyze", action="store_true", help="Auto-run analyzer after attack")
    
    args = parser.parse_args()
    
    # Log the start of chaos for the analyzer
    BUS_DIR.mkdir(parents=True, exist_ok=True)
    with open(BUS_DIR / "chaos_event.json", "w") as f:
        json.dump({
            "type": "chaos_injection",
            "timestamp": time.time(),
            "args": sys.argv[1:]
        }, f)

    if args.kill_mcp: kill_mcp()
    if args.corrupt_bus: corrupt_bus()
    if args.latency: inject_latency()
    if args.cpu: cpu_spike()
    if args.memory: memory_leak()
    
    print("🍌 Chaos Monkey: Attack complete.")
    
    if args.analyze:
        print("📊 Triggering Chaos Analyzer...")
        analyzer_script = Path(__file__).parent / "chaos_analyzer.py"
        subprocess.run([sys.executable, str(analyzer_script)])

if __name__ == "__main__":
    main()
