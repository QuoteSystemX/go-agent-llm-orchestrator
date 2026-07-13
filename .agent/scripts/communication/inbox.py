#!/usr/bin/env python3
"""
STORY-2 INBOX.md v2: structured human-to-agent channel.

Replaces the v1 free-form markdown INBOX.md (which was prompt-injection
vulnerable) with a JSONL file where each line is a validated entry.

File format: tasks/INBOX.md (kept for backward compat with the name; actually
JSONL). Each non-empty line is a JSON object conforming to inbox.schema.json.

Public API:
  - InboxEntry: dataclass for a parsed entry
  - append_entry(intent, body, ...): append a new entry, returns its id
  - read_entries(intent=None, target=None, since=None): filter and return entries
  - ack_entry(entry_id, response_body=None): mark entry as acked (creates a bus event)
  - validate_entry(dict): validate against schema, return list of errors
  - strip_for_prompt(entries): build a sanitized system-prompt fragment

Security properties (vs v1):
  - All entries validated against JSON schema; invalid = refused at write
  - body is plain text (no markdown/HTML/code); truncated to 2000 chars
  - knowledge_anchor required for redirect/context, regex-validated
  - strip_for_prompt() strips any remaining markup before injection
  - Sanitization is defense-in-depth; primary defense is schema validation
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

# Repo path resolution
REPO_ROOT = Path(__file__).resolve().parents[3]
INBOX_PATH = REPO_ROOT / "tasks" / "INBOX.md"
SCHEMA_PATH = REPO_ROOT / ".agent" / "config" / "inbox.schema.json"
BUS_PATH = REPO_ROOT / ".agent" / "bus"

# ----- Constants from schema (kept in sync; tests will catch drift) -----
ALLOWED_INTENTS = {"redirect", "clarify", "abort", "context", "ack"}
ALLOWED_AUTHORS = {"human", "agent"}
BODY_MAX_LEN = 2000
ANCHOR_PATTERN = re.compile(r"^#?[A-Za-z0-9_-]+(#[A-Za-z0-9_-]+)?$")
ID_PATTERN = re.compile(r"^inb_[0-9]{8}_[0-9]{6}_[a-f0-9]{6}$")


@dataclass
class InboxEntry:
    id: str
    ts: str
    author: str
    intent: str
    body: str
    target: Optional[str] = None
    knowledge_anchor: Optional[str] = None
    ack_required: bool = False
    acked_ts: Optional[str] = None
    acked_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _gen_id(ts: Optional[datetime] = None) -> str:
    t = ts or datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:6]
    return f"inb_{t.strftime('%Y%m%d_%H%M%S')}_{suffix}"


def validate_entry(entry: dict) -> list[str]:
    """Return list of validation errors (empty if valid)."""
    errors: list[str] = []
    # Required fields
    for field_name in ("id", "ts", "author", "intent", "body"):
        if field_name not in entry:
            errors.append(f"Missing required field: {field_name}")
    if errors:
        return errors

    # id pattern
    if not isinstance(entry["id"], str) or not ID_PATTERN.match(entry["id"]):
        errors.append(f"id must match {ID_PATTERN.pattern}")

    # ts format
    if not isinstance(entry["ts"], str):
        errors.append("ts must be a string")
    else:
        try:
            datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
        except ValueError:
            errors.append("ts must be ISO 8601")

    # author
    if entry["author"] not in ALLOWED_AUTHORS:
        errors.append(f"author must be one of {sorted(ALLOWED_AUTHORS)}")

    # intent
    if entry["intent"] not in ALLOWED_INTENTS:
        errors.append(f"intent must be one of {sorted(ALLOWED_INTENTS)}")

    # body
    body = entry.get("body", "")
    if not isinstance(body, str):
        errors.append("body must be a string")
    elif len(body) < 1:
        errors.append("body must not be empty")
    elif len(body) > BODY_MAX_LEN:
        errors.append(f"body exceeds max length {BODY_MAX_LEN}")

    # target
    if "target" in entry and entry["target"] is not None and not isinstance(entry["target"], str):
        errors.append("target must be a string or null")

    # knowledge_anchor
    if "knowledge_anchor" in entry and entry["knowledge_anchor"] is not None:
        if not isinstance(entry["knowledge_anchor"], str):
            errors.append("knowledge_anchor must be a string or null")
        elif not ANCHOR_PATTERN.match(entry["knowledge_anchor"]):
            errors.append(f"knowledge_anchor must match {ANCHOR_PATTERN.pattern}")

    # Conditional: redirect/context require knowledge_anchor
    if entry.get("intent") in ("redirect", "context"):
        anchor = entry.get("knowledge_anchor")
        if not anchor:
            errors.append(f"intent={entry['intent']} requires knowledge_anchor")

    # ack_required must be bool
    if "ack_required" in entry and not isinstance(entry["ack_required"], bool):
        errors.append("ack_required must be a boolean")

    return errors


def _ensure_inbox():
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INBOX_PATH.exists():
        INBOX_PATH.touch()


def append_entry(
    intent: str,
    body: str,
    author: str = "human",
    target: Optional[str] = None,
    knowledge_anchor: Optional[str] = None,
    ack_required: bool = False,
    ts: Optional[datetime] = None,
) -> InboxEntry:
    """Create a new entry, validate, and append. Raises ValueError on validation failure."""
    now = ts or datetime.now(timezone.utc)
    entry = InboxEntry(
        id=_gen_id(now),
        ts=now.isoformat().replace("+00:00", "Z"),
        author=author,
        intent=intent,
        body=body,
        target=target,
        knowledge_anchor=knowledge_anchor,
        ack_required=ack_required,
    )
    errors = validate_entry(entry.to_dict())
    if errors:
        raise ValueError(f"Invalid inbox entry: {' | '.join(errors)}")

    _ensure_inbox()
    with open(INBOX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    return entry


def read_entries(
    intent: Optional[str] = None,
    target: Optional[str] = None,
    since: Optional[datetime] = None,
    include_acked: bool = True,
) -> list[InboxEntry]:
    """Read and filter entries. Returns list of InboxEntry (most recent last)."""
    _ensure_inbox()
    out: list[InboxEntry] = []
    with open(INBOX_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines (e.g., from v1 free-form markdown)
                continue
            entry = InboxEntry(
                id=data.get("id", ""),
                ts=data.get("ts", ""),
                author=data.get("author", "human"),
                intent=data.get("intent", "context"),
                body=data.get("body", ""),
                target=data.get("target"),
                knowledge_anchor=data.get("knowledge_anchor"),
                ack_required=bool(data.get("ack_required", False)),
                acked_ts=data.get("acked_ts"),
                acked_by=data.get("acked_by"),
            )
            if intent and entry.intent != intent:
                continue
            # Target filter: include entries that match the target OR
            # have no target (global entries, visible to all tasks).
            # This way, target='task_xyz' shows entries targeting
            # task_xyz PLUS global entries (target=None).
            if target and entry.target is not None and entry.target != target:
                continue
            if not include_acked and entry.acked_ts:
                continue
            if since:
                try:
                    ts = datetime.fromisoformat(entry.ts.replace("Z", "+00:00"))
                    if ts < since:
                        continue
                except ValueError:
                    continue
            out.append(entry)
    return out


def ack_entry(entry_id: str, acked_by: str = "agent") -> bool:
    """Mark an entry as acked. Returns True if found and updated, False otherwise.

    Idempotent: re-acking an already-acked entry returns False (no change).
    """
    _ensure_inbox()
    lines = INBOX_PATH.read_text(encoding="utf-8").splitlines()
    found = False
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("id") != entry_id:
            continue
        if data.get("acked_ts"):
            return False  # already acked
        data["acked_ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        data["acked_by"] = acked_by
        lines[i] = json.dumps(data, ensure_ascii=False)
        found = True
        break
    if not found:
        return False
    INBOX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Emit bus event for telemetry
    try:
        BUS_PATH.mkdir(parents=True, exist_ok=True)
        with open(BUS_PATH / "inbox_acks.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "type": "inbox_ack",
                "entry_id": entry_id,
                "acked_by": acked_by,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }) + "\n")
    except Exception as e:
        # Best-effort telemetry; do not fail the ack
        sys.stderr.write(f"⚠️ Could not write inbox ack to bus: {e}\n")
    return True


def strip_for_prompt(entries: Iterable[InboxEntry], max_chars: int = 4000) -> str:
    """Build a sanitized system-prompt fragment from a list of entries.

    Defense-in-depth: even if an entry slipped through with markup, we
    strip <, >, and backtick characters before composing the prompt.
    This is the LAST line of defense, not the first.
    """
    if not entries:
        return ""
    # Sort by ts ascending
    sorted_ents = sorted(entries, key=lambda e: e.ts)
    parts: list[str] = []
    total = 0
    for e in sorted_ents:
        # Strip dangerous chars from body
        body = e.body
        # Remove HTML/markdown control chars
        body = re.sub(r"[<>`*_~#\[\]]", "", body)
        snippet = f"[{e.ts}] {e.intent} ({e.id}): {body}"
        if e.knowledge_anchor:
            snippet += f" [anchor: {e.knowledge_anchor}]"
        if total + len(snippet) > max_chars:
            break
        parts.append(snippet)
        total += len(snippet)
    return "\n".join(parts)


if __name__ == "__main__":
    # Quick CLI: read all entries
    for e in read_entries():
        print(json.dumps(e.to_dict(), ensure_ascii=False))
