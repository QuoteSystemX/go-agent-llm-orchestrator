#!/usr/bin/env python3
import sys
import json
import os
from pathlib import Path

CONFIG_PATH = Path(".agent/config/gateway_config.json")

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def expand_requirements(intent: str):
    config = load_config()
    ranking = config.get("gateway", {}).get("ranking_protocol", ["local_global_brain", "general_web_search"])
    
    print(f"📝 Starting Ranked Requirement Expansion for: '{intent}'")
    
    results = []
    
    for layer in ranking:
        print(f"  🔍 Checking {layer}...")
        
        if layer == "local_global_brain":
            # Real check: look into global standards folder
            standards_path = Path(os.environ.get("AGENT_GLOBAL_ROOT", "")) / "standards"
            # Simulated match for demo
            if "api" in intent.lower():
                results.append(f"[{layer.upper()}] Standard: Use RFC 7807 for error handling.")
                break # Found enough in Layer 1
                
        elif layer == "specialized_mcp":
            # Real check: check if MCP tools are available and enabled
            mcp_config = config.get("gateway", {}).get("mcp_servers", {})
            if mcp_config.get("github", {}).get("enabled"):
                # Simulated MCP call: search_github_code(intent)
                if "cache" in intent.lower():
                    results.append(f"[{layer.upper()}] Pattern: Implement exponential backoff for Redis reconnect.")
                    break # Found enough in Layer 2
                    
        elif layer == "general_web_search":
            # Real check: call search_web tool
            # results.append(search_web(f"best practices for {intent}"))
            results.append(f"[{layer.upper()}] Latest: Ensure TLS 1.3 for all outgoing connections.")

    if results:
        print("\n✅ EXPANDED REQUIREMENTS FOUND:")
        for r in results:
            print(f"  {r}")
    else:
        print("\n⚠️ No specific standards found across all layers.")

if __name__ == "__main__":
    expand_requirements(" ".join(sys.argv[1:]))
