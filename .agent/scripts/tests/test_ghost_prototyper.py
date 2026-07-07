#!/usr/bin/env python3
import unittest
import sys
import os
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

import analysis.ghost_prototyper as ghost

class TestGhostPrototyper(unittest.TestCase):
    @patch('sys.stdout', new_callable=MagicMock)
    def test_run_ghost_proto_success(self, mock_stdout):
        ghost.run_ghost_proto("Build a simple server")
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("feasible", output)

    @patch('sys.stdout', new_callable=MagicMock)
    @patch('analysis.ghost_prototyper._try_go_build', return_value=False)
    def test_run_ghost_proto_failure(self, mock_build, mock_stdout):
        result = ghost.run_ghost_proto("impossible task")
        self.assertFalse(result)
        output = "".join(call[0][0] for call in mock_stdout.write.call_args_list)
        self.assertIn("FAILED", output)

    @patch('analysis.ghost_prototyper.subprocess.run')
    @patch('analysis.ghost_prototyper.Path.read_text', return_value="hello world")
    @patch('analysis.ghost_prototyper.Path.write_text')
    @patch('analysis.ghost_prototyper.Path.exists', return_value=True)
    def test_run_isolated_worktree_success(self, mock_exists, mock_write_text, mock_read_text, mock_sub_run):
        # mock returns for subprocess runs inside run_isolated_worktree
        mock_sub_run.side_effect = [
            MagicMock(returncode=0, stdout=""), # git worktree list in cleanup
            MagicMock(returncode=0), # git worktree prune
            MagicMock(returncode=0), # git worktree add
            MagicMock(returncode=0), # go test
            MagicMock(returncode=0), # git worktree remove
            MagicMock(returncode=0), # git worktree prune
        ]
        
        success, metrics = ghost.run_isolated_worktree(
            file_path_str="foo.go",
            target="world",
            replacement="arbor",
            test_cmd="go test ./...",
            intent="test intent"
        )
        self.assertTrue(success)

    @patch('analysis.ghost_prototyper.subprocess.run')
    @patch('analysis.ghost_prototyper.Path.read_text', return_value="hello world")
    @patch('analysis.ghost_prototyper.Path.write_text')
    @patch('analysis.ghost_prototyper.Path.exists', return_value=True)
    def test_run_isolated_worktree_test_failure(self, mock_exists, mock_write_text, mock_read_text, mock_sub_run):
        # mock returns for subprocess runs inside run_isolated_worktree
        mock_sub_run.side_effect = [
            MagicMock(returncode=0, stdout=""), # git worktree list in cleanup
            MagicMock(returncode=0), # git worktree prune
            MagicMock(returncode=0), # git worktree add
            MagicMock(returncode=1, stdout="compile error", stderr="error details"), # go test fails
            MagicMock(returncode=0), # git worktree remove
            MagicMock(returncode=0), # git worktree prune
        ]
        
        success, metrics = ghost.run_isolated_worktree(
            file_path_str="foo.go",
            target="world",
            replacement="arbor",
            test_cmd="go test ./...",
            intent="test intent"
        )
        self.assertFalse(success)

    def test_parse_go_benchmarks(self):
        output = """
        goos: linux
        goarch: amd64
        pkg: github.com/QuoteSystemX/prompt-library
        cpu: Intel(R) Core(TM) i9-9900K CPU @ 3.60GHz
        BenchmarkMutexNoContention-8   20000000          65.4 ns/op        16 B/op        1 allocs/op
        BenchmarkMutexContention-8       500000         250.2 ns/op        32 B/op        2 allocs/op
        PASS
        ok      github.com/QuoteSystemX/prompt-library  3.123s
        """
        metrics = ghost.parse_go_benchmarks(output)
        self.assertEqual(metrics["count"], 2)
        self.assertAlmostEqual(metrics["ns_op"], 157.8)
        self.assertAlmostEqual(metrics["b_op"], 24.0)
        self.assertAlmostEqual(metrics["allocs_op"], 1.5)

if __name__ == "__main__":
    unittest.main()
