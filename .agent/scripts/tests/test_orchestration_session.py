#!/usr/bin/env python3
import unittest
import shutil
import json
import sys
import os
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.orchestration_session as orchestration_session

class TestOrchestrationSession(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_session_storage"
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        # Patch SHARED_DIR in the module
        self.patcher = patch('orchestration.orchestration_session.SHARED_DIR', self.test_root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_init_creates_session(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            sid = orchestration_session.init()
            self.assertEqual(fake_out.getvalue().strip(), sid)
            
            session_path = self.test_root / sid
            self.assertTrue(session_path.exists())
            self.assertTrue((session_path / "state.json").exists())

    def test_state_management(self):
        sid = orchestration_session.init()
        orchestration_session.set_state(sid, "test_key", "test_val")
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            orchestration_session.get_state(sid)
            state = json.loads(fake_out.getvalue().strip())
            self.assertEqual(state["test_key"], "test_val")

    def test_halt_session(self):
        sid = orchestration_session.init()
        orchestration_session.halt(sid)
        self.assertTrue((self.test_root / sid / "HALT").exists())

    def test_close_session(self):
        sid = orchestration_session.init()
        orchestration_session.close(sid)
        self.assertFalse((self.test_root / sid).exists())

if __name__ == "__main__":
    unittest.main()
