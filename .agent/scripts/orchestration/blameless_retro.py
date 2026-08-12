#!/usr/bin/env python3
"""Blameless Post-Mortem / Retrospective — cross-incident pattern detection.

war_room_manager.py resolves incidents in the moment (diagnose -> fix ->
validate -> commit -> report) and appends a durable record to
.agent/logs/incidents.jsonl for each one. This script looks *backward* across
that log for systemic patterns War Room's per-incident loop can't see:

  1. Pull incidents resolved in the trailing period (default 7 days).
  2. Group by root_cause_signature (an LLM-assigned kebab-case tag written by
     the debugger agent during diagnosis — NOT text/embedding similarity on
     the raw error, which tends to cluster by symptom rather than cause).
  3. For any root cause appearing 2+ times, spawn a small two-hop retro
     (debugger confirms the pattern -> sre-engineer proposes a structural
     fix) and write the result as an ADR in wiki/decisions/.
  4. Mechanically redact agent/branch/PR/author identifiers from the ADR
     text before writing — blameless by construction, not just by prompt
     wording.

Idempotent: a root-cause group is retro'd once per exact set of incident IDs
(tracked in .agent/logs/retro_state.json) — re-running (e.g. next week's
cron tick) won't re-fire for incidents already covered, only for the delta.

Usage:
  python3 blameless_retro.py                  # trailing 7 days, real run
  python3 blameless_retro.py --days 14
  python3 blameless_retro.py --dry-run         # show what would fire, no ADR/agent calls
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
for _domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
    _d_path = str(_SCRIPTS_DIR / _domain)
    if _d_path not in sys.path:
        sys.path.append(_d_path)

try:
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, save_json_atomic
    from lib.llm_client import call_mcp_broker
except ImportError:
    sys.path.append(str(_SCRIPTS_DIR.parent))
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, save_json_atomic
    from lib.llm_client import call_mcp_broker

INCIDENTS_LOG = REPO_ROOT / ".agent" / "logs" / "incidents.jsonl"
# NOT under .agent/logs/ — that whole directory is gitignored, but this state
# must survive a fresh CI checkout each week for the idempotency check below
# to work (a still-in-window incident set would otherwise look "new" again).
RETRO_STATE = REPO_ROOT / ".agent" / "config" / "retro_state.json"
DECISIONS_DIR = REPO_ROOT / "wiki" / "decisions"
AGENTS_DIR = REPO_ROOT / ".agent" / "agents"

MIN_OCCURRENCES = 2


# ── Data loading ────────────────────────────────────────────────────────────

def _load_incidents(since: datetime) -> list[dict]:
    if not INCIDENTS_LOG.exists():
        return []
    incidents = []
    with open(INCIDENTS_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = rec.get("ts", "")
            try:
                rec_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if rec_dt >= since:
                incidents.append(rec)
    return incidents


def _group_by_root_cause(incidents: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for inc in incidents:
        sig = (inc.get("root_cause_signature") or "unknown").strip().lower()
        if sig == "unknown":
            continue  # can't group what wasn't tagged — not a real signature
        groups.setdefault(sig, []).append(inc)
    return {sig: incs for sig, incs in groups.items() if len(incs) >= MIN_OCCURRENCES}


# ── Idempotency ──────────────────────────────────────────────────────────────

def _group_key(root_cause: str, incidents: list[dict]) -> str:
    """Stable key for a (root_cause, exact incident set) pair."""
    ids = sorted(inc["incident_id"] for inc in incidents)
    digest = hashlib.sha256(",".join(ids).encode()).hexdigest()[:12]
    return f"{root_cause}:{digest}"


def _already_processed(key: str) -> bool:
    state = load_json_safe(RETRO_STATE) or {"processed": []}
    return key in state.get("processed", [])


def _mark_processed(key: str) -> None:
    state = load_json_safe(RETRO_STATE) or {"processed": []}
    state.setdefault("processed", []).append(key)
    save_json_atomic(RETRO_STATE, state)


# ── Blameless redaction ──────────────────────────────────────────────────────

def _known_agent_names() -> list[str]:
    if not AGENTS_DIR.exists():
        return []
    return sorted({p.stem for p in AGENTS_DIR.rglob("*.md")}, key=len, reverse=True)


def redact_blameless(text: str) -> str:
    """Mechanically strip agent/branch/PR/author identifiers.

    A prompt instruction alone doesn't reliably stop an LLM from naming an
    agent or PR (flagged by the Council of Sages red-team pass on this
    proposal) — this is the mechanical backstop.
    """
    redacted = text

    # Agent names -> [agent]. Longest names first so e.g. "crypto-go-architect"
    # matches before "go-architect" would (if such a substring existed).
    for name in _known_agent_names():
        redacted = re.sub(rf"\b{re.escape(name)}\b", "[agent]", redacted, flags=re.IGNORECASE)

    # fix/inc-<id> branch names -> [branch]
    redacted = re.sub(r"fix/inc-[\w-]+", "[branch]", redacted)

    # PR references: "PR #123", "#123", "pull request 123"
    redacted = re.sub(r"\b(?:PR|pull request)\s*#?\d+\b", "[PR]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?<!\w)#\d+\b", "[PR]", redacted)

    # git author identity: email addresses, Co-Authored-By lines
    redacted = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[author]", redacted)
    redacted = re.sub(r"^Co-Authored-By:.*$", "[author]", redacted, flags=re.MULTILINE)

    return redacted


# ── Agent calls ──────────────────────────────────────────────────────────────

def _call_agent(agent_name: str, task: str) -> str:
    result = call_mcp_broker("call_agent", {"agent_name": agent_name, "task": task})
    return result.get("response", "")


def _run_retro(root_cause: str, incidents: list[dict]) -> str:
    """Two-hop retro: debugger confirms the pattern, sre-engineer proposes
    the structural fix. Returns raw (not yet redacted) ADR body text.
    """
    incident_lines = "\n".join(
        f"- {inc['incident_id']} ({inc.get('ts', '?')}): {inc.get('diagnosis_summary', 'n/a')} "
        f"-> fix: {inc.get('fix_summary', 'n/a')} [{inc.get('status', '?')}]"
        for inc in incidents
    )

    debugger_task = (
        f"Root cause signature '{root_cause}' was tagged on {len(incidents)} separate incidents "
        f"resolved by War Room:\n{incident_lines}\n\n"
        "Confirm whether these genuinely share the same underlying root cause (not just similar "
        "symptoms), and summarize the mechanism in 2-3 sentences. Do not name which agent or PR "
        "fixed each incident — describe the mechanism only."
    )
    pattern_confirmation = _call_agent("debugger", debugger_task)

    sre_task = (
        f"A recurring root cause ('{root_cause}') has been confirmed across {len(incidents)} "
        f"incidents:\n\n{pattern_confirmation}\n\n"
        "Propose a STRUCTURAL fix — something that prevents this class of failure going forward, "
        "not another point patch. Write it as an ADR body with these sections: "
        "## Context and Problem Statement, ## Decision Drivers, ## Considered Options, "
        "## Decision Outcome, ## Consequences. Do not name which agent or PR fixed any prior "
        "occurrence — describe the mechanism and the structural fix only."
    )
    return _call_agent("sre-engineer", sre_task)


# ── ADR writing ──────────────────────────────────────────────────────────────

def _next_adr_id() -> int:
    existing = [
        int(m.group(1))
        for p in DECISIONS_DIR.glob("ADR-*.md")
        if (m := re.match(r"ADR-(\d+)", p.name))
    ]
    return (max(existing) + 1) if existing else 1


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "retro"


def _write_adr(root_cause: str, incident_count: int, body: str, dry_run: bool) -> Path:
    adr_id = _next_adr_id()
    slug = _slugify(root_cause)
    filename = f"ADR-{adr_id:03d}-blameless-retro-{slug}.md"
    path = DECISIONS_DIR / filename

    content = (
        f"---\n"
        f"title: \"ADR {adr_id:03d} Blameless Retro {slug}\"\n"
        f"tags:\n  - blameless-retro\n"
        f"status: proposed\n"
        f"---\n\n"
        f"# ADR-{adr_id:03d}: Structural fix for recurring root cause: {root_cause}\n\n"
        f"> Generated by `blameless_retro.py` — a recurring root cause was detected across "
        f"{incident_count} War Room incidents in the trailing period. This ADR is blameless by "
        f"construction: agent names, branch names, PR references, and author identities are "
        f"mechanically redacted, not just prompt-instructed away.\n\n"
        f"{body}\n"
    )

    display_path = path.relative_to(REPO_ROOT) if REPO_ROOT in path.parents else path

    if dry_run:
        print(f"[DRY] would write {display_path} ({len(content)} chars)")
        return path

    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"✅ Wrote {display_path}")
    return path


# ── Main ─────────────────────────────────────────────────────────────────────

def run(days: int, dry_run: bool) -> list[Path]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    incidents = _load_incidents(since)
    print(f"📋 {len(incidents)} incident(s) in the trailing {days} day(s).")

    groups = _group_by_root_cause(incidents)
    if not groups:
        print("✅ No root cause recurred 2+ times — nothing to retro.")
        return []

    written = []
    for root_cause, incs in groups.items():
        key = _group_key(root_cause, incs)
        if _already_processed(key):
            print(f"⏭  '{root_cause}' ({len(incs)}x) already retro'd for this incident set — skipping.")
            continue

        print(f"🔁 '{root_cause}' recurred {len(incs)}x — running retro...")
        if dry_run:
            print(f"[DRY] would call debugger + sre-engineer for '{root_cause}'")
            continue

        raw_body = _run_retro(root_cause, incs)
        redacted_body = redact_blameless(raw_body)
        path = _write_adr(root_cause, len(incs), redacted_body, dry_run=False)
        _mark_processed(key)
        written.append(path)

    return written


def main():
    parser = argparse.ArgumentParser(description="Blameless cross-incident retrospective")
    parser.add_argument("--days", type=int, default=7, help="Trailing period to scan (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would fire without calling agents or writing ADRs")
    args = parser.parse_args()
    run(args.days, args.dry_run)


if __name__ == "__main__":
    main()
