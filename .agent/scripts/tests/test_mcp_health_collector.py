#!/usr/bin/env python3
import unittest
import shutil
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import health.mcp_health_collector as mcp_health

class TestMCPHealthCollector(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_mcp_health").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.config_dir = self.test_root / ".agent" / "config"
        self.config_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    @patch('pathlib.Path.resolve')
    def test_collect_missing_config(self, mock_resolve):
        # Mock resolve().parents[3] to point to test_root
        mock_resolve.return_value.parents = [None, None, None, self.test_root]
        
        collector = mcp_health.MCPHealthCollector()
        with patch('sys.stdout', new=MagicMock()):
            collector.collect()
            
        self.assertEqual(collector.status, "WARN")

    @patch('health.mcp_health_collector.check_mcp_health')
    @patch('pathlib.Path.resolve')
    def test_collect_with_servers(self, mock_resolve, mock_check):
        mock_resolve.return_value.parents = [None, None, None, self.test_root]
        
        (self.config_dir / "mcp_config.json").write_text(json.dumps({
            "mcpServers": {
                "server1": {"command": "echo", "args": ["1"]},
                "server2": {"command": "echo", "args": ["2"]}
            }
        }))
        
        # Mock check_mcp_health to return (True, "OK") for server1 and (False, "Fail") for server2
        def side_effect(name, cmd):
            if name == "server1":
                return True, "OK"
            return False, "Fail"
        mock_check.side_effect = side_effect
        
        collector = mcp_health.MCPHealthCollector()
        
        # Suppress save() writing to non-existent metrics dir by mocking add_metric and save or ensuring metrics dir exists
        (self.test_root / ".agent" / "metrics").mkdir(parents=True, exist_ok=True)
        # However, MetricCollector uses its own REPO_ROOT logic which might break.
        # Let's mock MetricCollector methods instead.
        collector.save = MagicMock()
        collector.add_metric = MagicMock()
        
        with patch('sys.stdout', new=MagicMock()):
            collector.collect()
            
        self.assertEqual(collector.status, "WARN") # because server2 failed
        self.assertEqual(collector.add_metric.call_count, 2)
        
        # Verify server1
        collector.add_metric.assert_any_call("svc_server1", "UP", "PASS")
        # Verify server2
        collector.add_metric.assert_any_call("svc_server2", "DOWN", "WARN")

if __name__ == "__main__":
    unittest.main()
