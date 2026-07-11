#!/usr/bin/env python3
"""
STORY-6 Knowledge Re-Injection — closes the distillation loop.

After lessons are distilled into LESSONS_LEARNED.md, this module
re-injects them into the next session's context (via the daemon's
system prompt fragment).

Lifecycle:
  1. archivist_trigger.py runs → produces fresh lessons
  2. emit_lesson_applied_event() called → lesson marked as "applied"
  3. On next session start, daemon calls build_knowledge_fragment()
  4. Fragment is prepended to task description (similar to INBOX)
  5. After N sessions without re-application, prune_stale_lessons()
     retires the lesson

Telemetry:
  - Each lesson tracks `applied_count` in LESSONS_LEARNED.md frontmatter
  - Bus event 'lesson_applied' is emitted on each re-application

Public API:
  - register_lesson(lesson_id, scope, ttl_days): mark for re-injection
  - build_knowledge_fragment(scope='global', max_chars=4000): prompt fragment
  - emit_lesson_applied_event(lesson_id, scope, session_id): bus event
  - prune_stale_lessons(): remove lessons with applied_count=0 and ttl expired
"""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
LESSONS_PATH = REPO_ROOT / "LESSONS_LEARNED.md"
SENTINEL_DIR = REPO_ROOT / ".agent" / "bus"
APPLIED_LOG = SENTINEL_DIR / "lesson_applied.jsonl"
INJECTION_INDEX = SENTINEL_DIR / "knowledge_injections.json"


# ----- Lesson injection registry -----
# Each injection is a {lesson_id, scope, ttl, registered_ts, applied_count}
# Stored in a JSON file. Persistent across sessions.

def _load_index() -> dict:
    if not INJECTION_INDEX.exists():
        return {"injections": []}
    try:
        return json.loads(INJECTION_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"injections": []}


def _save_index(idx: dict) -> None:
    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    INJECTION_INDEX.write_text(
        json.dumps(idx, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def register_lesson(lesson_id: str, scope: str = "global", ttl_days: int = 30) -> dict:
    """Register a lesson for re-injection.

    If the lesson is already registered, updates the TTL.
    """
    idx = _load_index()
    now = datetime.now(timezone.utc)
    for inj in idx["injections"]:
        if inj["lesson_id"] == lesson_id and inj["scope"] == scope:
            inj["registered_ts"] = now.isoformat()
            inj["ttl_days"] = ttl_days
            inj["applied_count"] = inj.get("applied_count", 0)
            _save_index(idx)
            return inj
    new = {
        "injection_id": f"inj_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}",
        "lesson_id": lesson_id,
        "scope": scope,
        "registered_ts": now.isoformat(),
        "ttl_days": ttl_days,
        "applied_count": 0,
    }
    idx["injections"].append(new)
    _save_index(idx)
    return new


def unregister_lesson(lesson_id: str, scope: str = "global") -> bool:
    """Remove a lesson from the injection index. Returns True if removed."""
    idx = _load_index()
    before = len(idx["injections"])
    idx["injections"] = [
        i for i in idx["injections"]
        if not (i["lesson_id"] == lesson_id and i["scope"] == scope)
    ]
    if len(idx["injections"]) < before:
        _save_index(idx)
        return True
    return False


def list_active(scope: str = "global") -> list[dict]:
    """Return active (non-expired) injections for the given scope."""
    idx = _load_index()
    now = datetime.now(timezone.utc)
    out = []
    for inj in idx["injections"]:
        if inj.get("scope") != scope:
            continue
        reg_ts = datetime.fromisoformat(inj["registered_ts"])
        expires = reg_ts + timedelta(days=inj["ttl_days"])
        if expires < now:
            continue
        out.append(inj)
    return out


def emit_lesson_applied_event(lesson_id: str, scope: str, session_id: str) -> dict:
    """Record that a lesson was applied in a session. Increments applied_count."""
    idx = _load_index()
    now = datetime.now(timezone.utc)
    found = False
    for inj in idx["injections"]:
        if inj["lesson_id"] == lesson_id and inj["scope"] == scope:
            inj["applied_count"] = inj.get("applied_count", 0) + 1
            inj["last_applied_ts"] = now.isoformat()
            inj["last_session_id"] = session_id
            found = True
            break
    if found:
        _save_index(idx)
    # If not found, register_lesson (called below) will save on its own.
    else:
        new = register_lesson(lesson_id, scope=scope)
        # Increment applied_count on the freshly-registered entry
        new["applied_count"] = 1
        new["last_applied_ts"] = now.isoformat()
        new["last_session_id"] = session_id
        idx = _load_index()
        for inj in idx["injections"]:
            if inj["lesson_id"] == lesson_id and inj["scope"] == scope:
                inj["applied_count"] = 1
                inj["last_applied_ts"] = now.isoformat()
                inj["last_session_id"] = session_id
                break
        _save_index(idx)

    # Emit bus event
    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "lesson_applied",
        "lesson_id": lesson_id,
        "scope": scope,
        "session_id": session_id,
        "ts": now.isoformat(),
    }
    with open(APPLIED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def prune_stale_lessons() -> int:
    """Remove lessons with applied_count=0 AND ttl expired. Returns count removed."""
    idx = _load_index()
    now = datetime.now(timezone.utc)
    before = len(idx["injections"])
    kept = []
    for inj in idx["injections"]:
        reg_ts = datetime.fromisoformat(inj["registered_ts"])
        expires = reg_ts + timedelta(days=inj["ttl_days"])
        if expires < now and inj.get("applied_count", 0) == 0:
            continue  # stale, remove
        kept.append(inj)
    idx["injections"] = kept
    _save_index(idx)
    return before - len(kept)


# ----- Prompt fragment builder -----

# Parse LESSONS_LEARNED.md entries (Markdown H3 with date prefix)
ENTRY_RE = re.compile(
    r"^###\s*\[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?:\[(?P<tag>\w+)\])?\s*(?:\[(?P<skill>[\w-]+)\])?\s*(?P<title>.+?)$",
    re.MULTILINE,
)


def _parse_lessons_file(path: Path) -> list[dict]:
    """Parse LESSONS_LEARNED.md into a list of {date, tag, skill, title, body}."""
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    out = []
    # Split by ### to get each entry
    for match in ENTRY_RE.finditer(content):
        entry = {
            "date": match.group("date"),
            "tag": match.group("tag"),
            "skill": match.group("skill"),
            "title": match.group("title").strip(),
        }
        # Body: text from this match end to next ###
        start = match.end()
        next_match = ENTRY_RE.search(content, pos=start)
        end = next_match.start() if next_match else len(content)
        body = content[start:end].strip()
        entry["body"] = body[:500]  # cap body
        out.append(entry)
    return out


def build_knowledge_fragment(
    scope: str = "global",
    max_chars: int = 4000,
    max_entries: int = 5,
) -> str:
    """Build a sanitized system-prompt fragment of relevant lessons.

    Strategy:
      1. Get active injections for scope (TTL not expired)
      2. For each injection, look up the lesson in LESSONS_LEARNED.md
      3. If lesson exists, add to fragment
      4. Sort by recency, cap to max_entries and max_chars
    """
    active = list_active(scope=scope)
    if not active:
        return ""
    # Limit to most recent N
    active = sorted(active, key=lambda x: x["registered_ts"], reverse=True)[:max_entries]

    lessons = _parse_lessons_file(LESSONS_PATH)
    if not lessons:
        return ""

    # Index lessons by date for fast lookup
    by_date = {l["date"]: l for l in lessons}
    parts: list[str] = []
    total = 0
    for inj in active:
        # The injection's registered_ts may not match the lesson date exactly,
        # so we look up by lesson_id (date format) or by closest date.
        # For simplicity, we use the injection's "registered_ts" date prefix.
        reg_date = inj["registered_ts"][:10]  # YYYY-MM-DD
        lesson = by_date.get(reg_date)
        if not lesson:
            continue
        snippet = f"[{lesson['date']}] {lesson.get('tag', 'INFO')}: {lesson['title']}\n  {lesson['body'][:300]}"
        if total + len(snippet) > max_chars:
            break
        parts.append(snippet)
        total += len(snippet)
    if not parts:
        return ""
    return "## Distilled Lessons (auto-injected)\n\n" + "\n\n".join(parts)


if __name__ == "__main__":
    # CLI: show active injections
    import argparse
    p = argparse.ArgumentParser(description="STORY-6 knowledge re-injection CLI.")
    sub = p.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="List active injections")
    p_list.add_argument("--scope", default="global")

    p_register = sub.add_parser("register", help="Register a lesson for re-injection")
    p_register.add_argument("lesson_id", help="Date prefix YYYY-MM-DD or any unique ID")
    p_register.add_argument("--scope", default="global")
    p_register.add_argument("--ttl", type=int, default=30, help="TTL in days")

    p_prune = sub.add_parser("prune", help="Remove stale lessons (applied_count=0 + expired)")

    p_emit = sub.add_parser("emit", help="Emit a lesson_applied event")
    p_emit.add_argument("lesson_id")
    p_emit.add_argument("--scope", default="global")
    p_emit.add_argument("--session-id", default="manual")

    p_fragment = sub.add_parser("fragment", help="Build the knowledge fragment for prompt")

    args = p.parse_args()
    if args.cmd == "list":
        for inj in list_active(scope=args.scope):
            print(json.dumps(inj, ensure_ascii=False))
    elif args.cmd == "register":
        print(json.dumps(register_lesson(args.lesson_id, scope=args.scope, ttl_days=args.ttl), ensure_ascii=False))
    elif args.cmd == "prune":
        removed = prune_stale_lessons()
        print(f"Pruned {removed} stale injections")
    elif args.cmd == "emit":
        print(json.dumps(emit_lesson_applied_event(args.lesson_id, args.scope, args.session_id), ensure_ascii=False))
    elif args.cmd == "fragment":
        print(build_knowledge_fragment())
    else:
        p.print_help()
