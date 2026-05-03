#!/usr/bin/env python3
"""Tests for bus_manager.py — push, pull, list, delete operations."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import bus_manager


class TestBusManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.close()
        self.original_bus = bus_manager.BUS_FILE
        bus_manager.BUS_FILE = Path(self.tmp.name)
        # Start with empty bus
        with open(self.tmp.name, "w") as f:
            json.dump({"version": "1.0.0", "objects": []}, f)

    def tearDown(self):
        bus_manager.BUS_FILE = self.original_bus
        os.unlink(self.tmp.name)
        tmp_file = Path(self.tmp.name).with_suffix(".tmp")
        if tmp_file.exists():
            os.unlink(tmp_file)

    def test_push_and_pull(self):
        with patch("sys.stdout", new_callable=StringIO):
            bus_manager.push("test_001", "requirement", "orchestrator", '{"spec": "test"}')

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            bus_manager.pull("test_001")
        output = mock_out.getvalue()
        data = json.loads(output)
        self.assertEqual(data["id"], "test_001")
        self.assertEqual(data["type"], "requirement")
        self.assertEqual(data["content"]["spec"], "test")

    def test_push_duplicate_fails(self):
        with patch("sys.stdout", new_callable=StringIO):
            bus_manager.push("dup_001", "memory_note", "test", '"hello"')

        with self.assertRaises(SystemExit):
            with patch("sys.stdout", new_callable=StringIO):
                bus_manager.push("dup_001", "memory_note", "test", '"world"')

    def test_pull_nonexistent_fails(self):
        with self.assertRaises(SystemExit):
            with patch("sys.stdout", new_callable=StringIO):
                bus_manager.pull("nonexistent")

    def test_delete(self):
        with patch("sys.stdout", new_callable=StringIO):
            bus_manager.push("del_001", "code_chunk", "test", '"code"')
            bus_manager.delete("del_001")

        with self.assertRaises(SystemExit):
            with patch("sys.stdout", new_callable=StringIO):
                bus_manager.pull("del_001")

    def test_clear(self):
        with patch("sys.stdout", new_callable=StringIO):
            bus_manager.push("clear_001", "memory_note", "test", '"a"')
            bus_manager.push("clear_002", "memory_note", "test", '"b"')
            bus_manager.clear()

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            bus_manager.list_objects()
        self.assertIn("empty", mock_out.getvalue())

    def test_plain_text_content(self):
        """Non-JSON content should be wrapped as {"text": ...}"""
        with patch("sys.stdout", new_callable=StringIO):
            bus_manager.push("txt_001", "memory_note", "test", "plain text note")

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            bus_manager.pull("txt_001")
        data = json.loads(mock_out.getvalue())
        self.assertEqual(data["content"]["text"], "plain text note")

    def test_invalid_type_fails(self):
        with self.assertRaises(SystemExit):
            with patch("sys.stdout", new_callable=StringIO):
                bus_manager.push("bad_001", "invalid_type", "test", '"x"')


if __name__ == "__main__":
    unittest.main()
