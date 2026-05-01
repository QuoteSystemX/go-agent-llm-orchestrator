import sys
from pathlib import Path
import unittest

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS_DIR))

from lib.paths import REPO_ROOT
from guardrail_monitor import _split_commands, check_secret_leak, _is_command_match

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
