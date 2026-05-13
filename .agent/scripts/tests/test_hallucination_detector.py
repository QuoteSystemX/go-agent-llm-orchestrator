#!/usr/bin/env python3
import unittest
import shutil
import sys
import json
import os
import time
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

import health.hallucination_detector as detector

class TestHallucinationDetector(unittest.TestCase):
    def setUp(self):
        self.test_root = (REPO_ROOT / "scratch" / "test_hallucination").resolve()
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)
        
        self.bus_dir = self.test_root / ".agent" / "bus"
        self.bus_dir.mkdir(parents=True)
        
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        # Patch paths
        self.patch_root = patch('health.hallucination_detector.REPO_ROOT', self.test_root)
        self.patch_bus = patch('health.hallucination_detector.BUS_DIR', self.bus_dir)
        self.patch_root.start()
        self.patch_bus.start()

    def tearDown(self):
        self.patch_root.stop()
        self.patch_bus.stop()
        os.chdir(self.old_cwd)
        if self.test_root.exists():
            shutil.rmtree(self.test_root)

    def test_extract_signatures(self):
        content = "def func1(a): pass\nfunc func2() {}"
        sigs = detector.extract_signatures(content)
        self.assertIn("func1", sigs)
        self.assertIn("func2", sigs)

    def test_detect_hallucination_missing_func(self):
        spec = self.test_root / "spec.md"
        spec.write_text("Should implement def my_func()")
        
        impl = self.test_root / "impl.py"
        impl.write_text("def other_func(): pass")
        
        discrepancies = detector.detect_hallucination(impl, spec)
        self.assertTrue(any("my_func" in d for d in discrepancies))

    def test_validate_references_invalid(self):
        # Create one valid script
        script_dir = self.test_root / ".agent" / "scripts"
        script_dir.mkdir(parents=True)
        (script_dir / "valid.py").write_text("# Valid")
        
        refs = ["valid.py", "ghost.py"]
        results = detector.validate_references(refs)
        
        self.assertTrue(results[0]["exists"]) # valid.py exists
        self.assertFalse(results[1]["exists"]) # ghost.py doesn't

    def test_audit_recent_files(self):
        wiki_dir = self.test_root / "wiki"
        wiki_dir.mkdir()
        wiki_file = wiki_dir / "Architecture.md"
        # Reference a ghost script
        wiki_file.write_text("Uses ghost_script.py")
        
        # Ensure it's "recent"
        os.utime(wiki_file, (time.time(), time.time()))
        
        flagged = detector.audit_recent_files()
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["hallucinated_scripts"], ["ghost_script.py"])

if __name__ == "__main__":
    unittest.main()
