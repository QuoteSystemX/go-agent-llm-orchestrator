#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]
    sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev", "misc"]:
        sys.path.append(str(REPO_ROOT / ".agent" / "scripts" / domain))

import orchestration.blameless_retro as retro


def _incident(incident_id, root_cause, ts=None, **extra):
    ts = ts or datetime.now(timezone.utc).isoformat()
    rec = {
        "incident_id": incident_id,
        "ts": ts,
        "root_cause_signature": root_cause,
        "diagnosis_summary": extra.get("diagnosis_summary", "diag"),
        "fix_summary": extra.get("fix_summary", "fix"),
        "branch": extra.get("branch", f"fix/inc-{incident_id}"),
        "status": extra.get("status", "committed"),
    }
    return rec


class TestGroupingAndIdempotency(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.incidents_log = self.tmp_dir / "incidents.jsonl"
        self.retro_state = self.tmp_dir / "retro_state.json"
        self.decisions_dir = self.tmp_dir / "wiki_decisions"
        self.decisions_dir.mkdir()
        self.patches = [
            patch('orchestration.blameless_retro.INCIDENTS_LOG', self.incidents_log),
            patch('orchestration.blameless_retro.RETRO_STATE', self.retro_state),
            patch('orchestration.blameless_retro.DECISIONS_DIR', self.decisions_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_log(self, records):
        with open(self.incidents_log, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_single_occurrence_not_grouped(self):
        self._write_log([_incident("inc_1", "missing-timeout-default")])
        incidents = retro._load_incidents(datetime.now(timezone.utc) - timedelta(days=7))
        groups = retro._group_by_root_cause(incidents)
        self.assertEqual(groups, {})

    def test_two_occurrences_grouped(self):
        self._write_log([
            _incident("inc_1", "missing-timeout-default"),
            _incident("inc_2", "missing-timeout-default"),
            _incident("inc_3", "unrelated-cause"),
        ])
        incidents = retro._load_incidents(datetime.now(timezone.utc) - timedelta(days=7))
        groups = retro._group_by_root_cause(incidents)
        self.assertIn("missing-timeout-default", groups)
        self.assertEqual(len(groups["missing-timeout-default"]), 2)
        self.assertNotIn("unrelated-cause", groups)  # only 1 occurrence

    def test_unknown_signature_never_grouped(self):
        self._write_log([
            _incident("inc_1", "unknown"),
            _incident("inc_2", "unknown"),
            _incident("inc_3", "unknown"),
        ])
        incidents = retro._load_incidents(datetime.now(timezone.utc) - timedelta(days=7))
        groups = retro._group_by_root_cause(incidents)
        self.assertEqual(groups, {})

    def test_signature_case_and_whitespace_normalized(self):
        self._write_log([
            _incident("inc_1", "  Missing-Timeout-Default  "),
            _incident("inc_2", "missing-timeout-default"),
        ])
        incidents = retro._load_incidents(datetime.now(timezone.utc) - timedelta(days=7))
        groups = retro._group_by_root_cause(incidents)
        self.assertEqual(len(groups), 1)
        self.assertIn("missing-timeout-default", groups)

    def test_outside_trailing_period_excluded(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self._write_log([
            _incident("inc_1", "missing-timeout-default", ts=old_ts),
            _incident("inc_2", "missing-timeout-default", ts=old_ts),
        ])
        incidents = retro._load_incidents(datetime.now(timezone.utc) - timedelta(days=7))
        self.assertEqual(incidents, [])

    def test_idempotent_same_incident_set_skipped(self):
        incs = [_incident("inc_1", "x"), _incident("inc_2", "x")]
        key = retro._group_key("x", incs)
        self.assertFalse(retro._already_processed(key))
        retro._mark_processed(key)
        self.assertTrue(retro._already_processed(key))

    def test_different_incident_set_same_root_cause_not_skipped(self):
        set_a = [_incident("inc_1", "x"), _incident("inc_2", "x")]
        set_b = [_incident("inc_1", "x"), _incident("inc_2", "x"), _incident("inc_3", "x")]
        key_a = retro._group_key("x", set_a)
        key_b = retro._group_key("x", set_b)
        self.assertNotEqual(key_a, key_b)
        retro._mark_processed(key_a)
        self.assertTrue(retro._already_processed(key_a))
        self.assertFalse(retro._already_processed(key_b))  # the delta (inc_3) should still fire

    def test_end_to_end_run_writes_adr_and_marks_processed(self):
        self._write_log([
            _incident("inc_1", "missing-timeout-default"),
            _incident("inc_2", "missing-timeout-default"),
        ])
        with patch('orchestration.blameless_retro._call_agent') as mock_call:
            mock_call.side_effect = [
                "These incidents share the same root cause: a missing default timeout.",
                "## Context and Problem Statement\nSome requests hang indefinitely.\n"
                "## Decision Outcome\nAdd a default timeout constant.\n",
            ]
            written = retro.run(days=7, dry_run=False)

        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].exists())
        content = written[0].read_text()
        self.assertIn("missing-timeout-default", content)
        self.assertIn("Add a default timeout constant", content)
        self.assertEqual(mock_call.call_count, 2)  # debugger + sre-engineer

        # Second run with the same incidents should skip (already processed)
        with patch('orchestration.blameless_retro._call_agent') as mock_call_2:
            written_2 = retro.run(days=7, dry_run=False)
        self.assertEqual(written_2, [])
        mock_call_2.assert_not_called()

    def test_dry_run_never_calls_agents_or_writes(self):
        self._write_log([
            _incident("inc_1", "missing-timeout-default"),
            _incident("inc_2", "missing-timeout-default"),
        ])
        with patch('orchestration.blameless_retro._call_agent') as mock_call:
            written = retro.run(days=7, dry_run=True)
        mock_call.assert_not_called()
        self.assertEqual(written, [])
        self.assertEqual(list(self.decisions_dir.glob("*.md")), [])


class TestRedaction(unittest.TestCase):
    @patch('orchestration.blameless_retro._known_agent_names', return_value=["debugger", "sre-engineer", "backend-specialist"])
    def test_redacts_agent_names(self, _mock):
        text = "The debugger agent found the issue, then sre-engineer proposed the fix."
        out = retro.redact_blameless(text)
        self.assertNotIn("debugger", out)
        self.assertNotIn("sre-engineer", out)
        self.assertIn("[agent]", out)

    @patch('orchestration.blameless_retro._known_agent_names', return_value=[])
    def test_redacts_branch_names(self, _mock):
        text = "The fix landed on fix/inc-inc_1783632997 after validation."
        out = retro.redact_blameless(text)
        self.assertNotIn("fix/inc-inc_1783632997", out)
        self.assertIn("[branch]", out)

    @patch('orchestration.blameless_retro._known_agent_names', return_value=[])
    def test_redacts_pr_references(self, _mock):
        for text in ["See PR #42 for details.", "Fixed in #17.", "pull request 99 resolved it."]:
            out = retro.redact_blameless(text)
            self.assertIn("[PR]", out)

    @patch('orchestration.blameless_retro._known_agent_names', return_value=[])
    def test_redacts_author_identity(self, _mock):
        text = "Reported by artur@example.com.\nCo-Authored-By: Someone <someone@example.com>"
        out = retro.redact_blameless(text)
        self.assertNotIn("artur@example.com", out)
        self.assertNotIn("someone@example.com", out)

    @patch('orchestration.blameless_retro._known_agent_names', return_value=[])
    def test_preserves_unrelated_text(self, _mock):
        text = "The root cause was a missing default timeout in the HTTP client."
        out = retro.redact_blameless(text)
        self.assertEqual(text, out)


class TestNextAdrId(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.patch_dir = patch('orchestration.blameless_retro.DECISIONS_DIR', self.tmp_dir)
        self.patch_dir.start()

    def tearDown(self):
        self.patch_dir.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_empty_dir_starts_at_1(self):
        self.assertEqual(retro._next_adr_id(), 1)

    def test_picks_max_plus_one(self):
        (self.tmp_dir / "ADR-007-foo.md").write_text("")
        (self.tmp_dir / "ADR-053-bar.md").write_text("")
        (self.tmp_dir / "ADR-012-baz.md").write_text("")
        self.assertEqual(retro._next_adr_id(), 54)


if __name__ == "__main__":
    unittest.main()
