#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.agent_skill_auditor as skill_auditor

class TestAgentSkillAuditor(unittest.TestCase):
    def setUp(self):
        self.test_root = REPO_ROOT / "scratch" / "test_skill_audit"
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root)
        self.test_root.mkdir(parents=True)

    def tearDown(self):
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root)

    def test_audit_agent_compliant(self):
        agent_file = self.test_root / "good-agent.md"
        agent_file.write_text("---\nskills: clean-code, dev\n---\nHello")
        
        issues = skill_auditor.audit_agent(agent_file)
        self.assertEqual(len(issues), 0)

    def test_audit_agent_missing_fm(self):
        agent_file = self.test_root / "bad-agent.md"
        agent_file.write_text("Hello")
        
        issues = skill_auditor.audit_agent(agent_file)
        self.assertIn("Missing frontmatter (---)", issues)

    def test_audit_agent_missing_mandatory_skill(self):
        agent_file = self.test_root / "no-clean-code.md"
        agent_file.write_text("---\nskills: testing\n---\nHello")
        
        issues = skill_auditor.audit_agent(agent_file)
        self.assertIn("Missing mandatory skill: clean-code", issues)

    def test_audit_agent_tool_reference_no_skills(self):
        agent_file = self.test_root / "tools-no-skills.md"
        agent_file.write_text("---\nno-skills-field: here\n---\nRun `test.py`")
        
        issues = skill_auditor.audit_agent(agent_file)
        self.assertTrue(any("References tools" in i for i in issues))

if __name__ == "__main__":
    unittest.main()
