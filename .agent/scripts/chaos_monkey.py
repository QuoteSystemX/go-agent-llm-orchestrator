#!/usr/bin/env python3
"""
Chaos Monkey - Resilience Testing & Failure Injection
Intentionally injects failures into the orchestration pipeline to test stability.
"""
import os
import sys
import json
import random
import time
import subprocess
from pathlib import Path

# Safety Switch
CHAOS_ENABLED = os.environ.get("CHAOS_ENABLED") == "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
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

def main():
    if not CHAOS_ENABLED:
        print("❌ CHAOS DISABLED. Set CHAOS_ENABLED=1 to run.")
        sys.exit(0)

    import argparse
    parser = argparse.ArgumentParser(description="Chaos Monkey Failure Injector")
    parser.add_argument("--kill-mcp", action="store_true", help="Kill the MCP server")
    parser.add_argument("--corrupt-bus", action="store_true", help="Corrupt a random bus file")
    parser.add_argument("--latency", action="store_true", help="Inject 5s latency")
    
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
    
    print("🍌 Chaos Monkey: Attack complete.")

if __name__ == "__main__":
    main()
