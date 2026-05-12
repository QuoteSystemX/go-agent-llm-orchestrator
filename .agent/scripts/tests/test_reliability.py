
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

import sys
from pathlib import Path
import unittest

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

from lib.paths import REPO_ROOT
import health.guardrail_monitor; import sys; sys.modules['guardrail_monitor'] = sys.modules['health.guardrail_monitor']
from health.guardrail_monitor import _split_commands, check_secret_leak, _is_command_match

class TestReliability(unittest.TestCase):
    def test_command_splitting(self):
        cmd = "echo hi | grep hi && rm -rf /; $(whoami)"
        segments = _split_commands(cmd)
        self.assertIn("echo hi", segments)
        self.assertIn("grep hi", segments)
        self.assertIn("rm -rf /", segments)
        self.assertIn("whoami", segments)

    def test_secret_leak(self):
        self.assertTrue(check_secret_leak("export AWS_SECRET_ACCESS_KEY=1234567890123456789012345678901234567890")[0])
        self.assertTrue(check_secret_leak("password=mysecretpassword123")[0])
        self.assertFalse(check_secret_leak("echo hello")[0])

    def test_command_matching(self):
        self.assertTrue(_is_command_match("rm -rf", "rm -rf /tmp"))
        self.assertFalse(_is_command_match("rm -rf", "grep 'rm -rf' file.txt"))

if __name__ == "__main__":
    unittest.main()
