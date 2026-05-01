#!/usr/bin/env python3
"""Tests for experience_distiller.py — parsing, skill-tagging, and filtering."""
import sys
import os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from experience_distiller import parse_entries, extract_date, extract_skill_tag, filter_by_skill


SAMPLE_CONTENT = """# Lessons Learned

Some header text.

### [2026-04-28] [BUG] [go-patterns] xsync MapOf nil pointer on empty init
Always initialize xsync.MapOf with NewMapOf(), never with zero-value.

### [2026-04-28] [CORE] [shared-context] Initial Knowledge Setup
Context for project startup.

### [2026-04-30] [PERF] [go-patterns] pgx pool exhaustion under load
Set MaxConns to match expected concurrency, not higher.

### [2026-04-25] [WATCHDOG] [telemetry] Token budget exceeded
Monitor token usage with guardrail_monitor.py.
"""


class TestParseEntries(unittest.TestCase):
    def test_parses_all_entries(self):
        header, entries = parse_entries(SAMPLE_CONTENT)
        self.assertEqual(len(entries), 4)

    def test_header_preserved(self):
        header, _ = parse_entries(SAMPLE_CONTENT)
        self.assertIn("Lessons Learned", header)


class TestExtractDate(unittest.TestCase):
    def test_valid_date(self):
        entry = "[2026-04-28] [BUG] [go-patterns] Title"
        dt = extract_date(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 4)
        self.assertEqual(dt.day, 28)

    def test_no_date(self):
        entry = "Some random text without a date"
        dt = extract_date(entry)
        self.assertIsNone(dt)

    def test_invalid_date(self):
        entry = "[2026-13-45] Invalid"
        dt = extract_date(entry)
        self.assertIsNone(dt)


class TestExtractSkillTag(unittest.TestCase):
    def test_valid_skill_tag(self):
        entry = "[2026-04-28] [BUG] [go-patterns] Title"
        tag = extract_skill_tag(entry)
        self.assertEqual(tag, "go-patterns")

    def test_shared_context_tag(self):
        entry = "[2026-04-28] [CORE] [shared-context] Title"
        tag = extract_skill_tag(entry)
        self.assertEqual(tag, "shared-context")

    def test_no_skill_tag(self):
        entry = "[2026-04-28] [BUG] Title without skill"
        tag = extract_skill_tag(entry)
        self.assertIsNone(tag)

    def test_telemetry_tag(self):
        entry = "[2026-04-25] [WATCHDOG] [telemetry] Token budget"
        tag = extract_skill_tag(entry)
        self.assertEqual(tag, "telemetry")


class TestFilterBySkill(unittest.TestCase):
    def setUp(self):
        """Create a temporary LESSONS_LEARNED.md for testing."""
        import experience_distiller
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                               encoding="utf-8")
        self.tmp.write(SAMPLE_CONTENT)
        self.tmp.close()
        self.original_path = experience_distiller.LESSONS_PATH
        experience_distiller.LESSONS_PATH = Path(self.tmp.name)

    def tearDown(self):
        import experience_distiller
        experience_distiller.LESSONS_PATH = self.original_path
        os.unlink(self.tmp.name)

    def test_filter_go_patterns(self):
        result = filter_by_skill("go-patterns")
        self.assertIn("2 lesson(s)", result)
        self.assertIn("xsync", result)
        self.assertIn("pgx", result)

    def test_filter_telemetry(self):
        result = filter_by_skill("telemetry")
        self.assertIn("1 lesson(s)", result)
        self.assertIn("Token budget", result)

    def test_filter_nonexistent_skill(self):
        result = filter_by_skill("nonexistent-skill")
        self.assertIn("No lessons found", result)


if __name__ == "__main__":
    unittest.main()
