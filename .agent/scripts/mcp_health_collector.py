#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Antigravity Standard: Path Resolution
sys.path.append(str(Path(__file__).resolve().parent))
from lib.metrics_base import MetricCollector
from mcp_provisioner import check_mcp_health

class MCPHealthCollector(MetricCollector):
    """
    Collects health metrics for all MCP servers configured in mcp_config.json.
    Server checks run in parallel for speed.
    """
    def __init__(self):
        super().__init__("MCP_Health")

    def collect(self):
        root = Path(__file__).resolve().parents[2]
        config_path = root / ".agent" / "config" / "mcp_config.json"
        
        if not config_path.exists():
            print(f"⚠️ mcp_config.json not found at {config_path}")
            self.status = "WARN"
            self.save()
            return

        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load mcp_config.json: {e}")
            self.status = "FAIL"
            self.save()
            return

        mcp_servers = config.get("mcpServers", {})
        results = {}
        overall_fail = False

        def check_one(name_cfg):
            name, cfg = name_cfg
            cmd = cfg.get("command")
            args = cfg.get("args", [])
            
            if not cmd:
                return name, "MISSING_CMD", "WARN"
            
            full_cmd = [cmd] + args
            is_main = name == "local-skill-server"
            
            is_healthy, msg = check_mcp_health(name, None if is_main else full_cmd)
            status = "PASS" if is_healthy else "WARN"
            return name, "UP" if is_healthy else "DOWN", status

        # Parallel health checks for all MCP servers
        with ThreadPoolExecutor(max_workers=min(len(mcp_servers), 6)) as ex:
            futures = {ex.submit(check_one, (n, c)): n for n, c in mcp_servers.items()}
            for future in as_completed(futures):
                name, value, status = future.result()
                results[name] = value
                self.add_metric(f"svc_{name}", value, status)
                if status != "PASS":
                    print(f"⚠️ MCP Server '{name}' is {value}")
                    overall_fail = True
                else:
                    print(f"✅ MCP Server '{name}' is UP")

        self.status = "PASS" if not overall_fail else "WARN"
        self.save()
        print(f"✅ MCP Health metrics collected ({len(mcp_servers)} servers). Status: {self.status}")

if __name__ == "__main__":
    MCPHealthCollector().collect()
