#!/usr/bin/env python3
"""
inbox_validate.py — Companion script for the inbox-patterns skill.

Validates tasks/INBOX.md against the JSON Schema and reports issues.
Run before committing INBOX entries.

Usage:
    python3 inbox_validate.py [PATH_TO_INBOX]
    python3 inbox_validate.py                                  # default: tasks/INBOX.md
    python3 inbox_validate.py /path/to/INBOX.md --json
    python3 inbox_validate.py /path/to/INBOX.md --strict
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INBOX = REPO_ROOT / "tasks" / "INBOX.md"

# Mirrored from .agent/scripts/communication/inbox.py
ALLOWED_INTENTS = {"redirect", "clarify", "abort", "context", "ack"}
ALLOWED_AUTHORS = {"human", "agent"}
ID_PATTERN = re.compile(r"^inb_[0-9]{8}_[0-9]{6}_[a-f0-9]{6}$")
ANCHOR_PATTERN = re.compile(r"^#?[A-Za-z0-9_-]+(#[A-Za-z0-9_-]+)?$")
BODY_MAX_LEN = 2000


def validate_entry(entry: dict) -> list[str]:
    errors = []
    for field_name in ("id", "ts", "author", "intent", "body"):
        if field_name not in entry:
            errors.append(f"Missing required field: {field_name}")
    if errors:
        return errors

    if not isinstance(entry["id"], str) or not ID_PATTERN.match(entry["id"]):
        errors.append(f"id must match {ID_PATTERN.pattern}")

    if not isinstance(entry["ts"], str):
        errors.append("ts must be a string")
    else:
        try:
            from datetime import datetime
            datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
        except ValueError:
            errors.append("ts must be ISO 8601")

    if entry["author"] not in ALLOWED_AUTHORS:
        errors.append(f"author must be one of {sorted(ALLOWED_AUTHORS)}")

    if entry["intent"] not in ALLOWED_INTENTS:
        errors.append(f"intent must be one of {sorted(ALLOWED_INTENTS)}")

    body = entry.get("body", "")
    if not isinstance(body, str):
        errors.append("body must be a string")
    elif len(body) < 1:
        errors.append("body must not be empty")
    elif len(body) > BODY_MAX_LEN:
        errors.append(f"body exceeds max length {BODY_MAX_LEN}")

    if "target" in entry and entry["target"] is not None and not isinstance(entry["target"], str):
        errors.append("target must be a string or null")

    if "knowledge_anchor" in entry and entry["knowledge_anchor"] is not None:
        if not isinstance(entry["knowledge_anchor"], str):
            errors.append("knowledge_anchor must be a string or null")
        elif not ANCHOR_PATTERN.match(entry["knowledge_anchor"]):
            errors.append(f"knowledge_anchor must match {ANCHOR_PATTERN.pattern}")

    if entry.get("intent") in ("redirect", "context"):
        anchor = entry.get("knowledge_anchor")
        if not anchor:
            errors.append(f"intent={entry['intent']} requires knowledge_anchor")

    if "ack_required" in entry and not isinstance(entry["ack_required"], bool):
        errors.append("ack_required must be a boolean")

    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate tasks/INBOX.md (JSONL)")
    p.add_argument("inbox", nargs="?", default=None, help="Path to INBOX.md")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = p.parse_args()

    path = Path(args.inbox) if args.inbox else DEFAULT_INBOX
    if not path.exists():
        if args.json:
            print(json.dumps({"passed": False, "errors": [f"Not found: {path}"]}))
        else:
            print(f"❌ Inbox not found: {path}")
        return 2

    total = 0
    errors_by_line = []
    warnings = []

    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors_by_line.append({"line": lineno, "errors": [f"Invalid JSON: {e}"]})
                continue
            entry_errors = validate_entry(entry)
            if entry_errors:
                errors_by_line.append({"line": lineno, "errors": entry_errors})

    passed = len(errors_by_line) == 0 and (not warnings or not args.strict)

    if args.json:
        result = {
            "inbox_path": str(path),
            "total_entries": total,
            "errors": errors_by_line,
            "warnings": warnings,
            "passed": passed,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 INBOX validation: {path.name}")
        print(f"   Total entries: {total}")
        if errors_by_line:
            print(f"   ❌ {len(errors_by_line)} entry(ies) with errors:")
            for e in errors_by_line:
                print(f"      L{e['line']}: {e['errors']}")
        else:
            print(f"   ✅ All entries valid.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
