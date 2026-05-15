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

import context.bus_debugger as debugger

class TestBusDebugger(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_bus_debugger").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.bus_file = self.bus_dir / "context.json"
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.patch_file = patch('context.bus_debugger.BUS_FILE', self.bus_file)
        self.patch_file.start()

    def tearDown(self):
        self.patch_file.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_interactive_debug(self):
        # Create dummy bus file
        self.bus_file.write_text(json.dumps({
            "objects": [
                {"id": "123", "type": "task", "author": "system", "data": "test"}
            ]
        }))
        
        # Test sequences of inputs:
        # 1. list
        # 2. peek 123
        # 3. peek 999
        # 4. quit
        inputs = ["l", "p 123", "p 999", "q"]
        def mock_input(*args, **kwargs):
            if inputs:
                return inputs.pop(0)
            raise EOFError()
            
        with patch('builtins.input', mock_input):
            with patch('sys.stdout', new=MagicMock()) as mock_stdout:
                debugger.interactive_debug()
                
        # Just check it didn't crash
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
