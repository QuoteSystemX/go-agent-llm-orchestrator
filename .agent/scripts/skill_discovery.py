#!/usr/bin/env python3
"""Skill Discovery — JIT Skill Acquisition.

Fetches external documentation and prepares it for agent consumption.
Usage:
    python3 skill_discovery.py https://api.example.com/docs
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

def discover_skill(url):
    print(f"🌐 Fetching documentation from: {url}")
    
    try:
        # Use curl to fetch content (available on most systems)
        result = subprocess.run(
            ["curl", "-s", "-L", url],
            capture_output=True,
            text=True,
            check=True
        )
        content = result.stdout
        
        if not content:
            print("❌ Failed to fetch content: Empty response.")
            return False
            
        print(f"✅ Fetched {len(content)} characters.")
        
        # Create a discovery DTO for the agent to process
        bus_dir = Path(".agent/bus/outputs")
        bus_dir.mkdir(parents=True, exist_ok=True)
        
        discovery_dto = {
            "timestamp": datetime.now().isoformat(),
            "agent": "skill-discovery",
            "goal": f"Import skill from {url}",
            "status": "pending_synthesis",
            "source_url": url,
            "raw_content_preview": content[:2000], # Send a preview to the bus
            "full_content_path": str(Path(".agent/bus/temp_docs.txt"))
        }
        
        # Save full content temporarily for the agent to read
        with open(".agent/bus/temp_docs.txt", "w") as f:
            f.write(content)
            
        filename = f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(bus_dir / filename, "w") as f:
            json.dump(discovery_dto, f, indent=2)
            
        print(f"📝 Discovery DTO saved to: .agent/bus/outputs/{filename}")
        print("🤖 Agent @analyst or @orchestrator should now synthesize the SKILL.md.")
        
        return True
    except Exception as e:
        print(f"❌ Error during discovery: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 skill_discovery.py <url>")
        sys.exit(1)
    
    success = discover_skill(sys.argv[1])
    sys.exit(0 if success else 1)
