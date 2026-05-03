#!/usr/bin/env python3
"""
quality_tracker.py — Agent quality monitoring via GitHub PR labels

Two modes:
  1. --record-event: called by agent-quality.yml on each PR event (writes JSONL log)
  2. --output FILE:  called by agent-feedback.yml weekly (aggregates log → markdown report)

Label convention (set by human reviewers on agent-generated PRs):
  agent-generated    — marks any PR created by an agent (required for tracking)
  agent:excellent    — merged as-is, no significant review comments
  agent:ok           — merged after minor revisions
  agent:revised      — merged after major revisions
  agent:rejected     — closed without merging

Agent identity label (set by the agent itself when creating PR):
  agent:<name>       — e.g. agent:debugger, agent:backend-specialist

Usage:
  # Record a PR event (called from CI):
  python3 .agent/scripts/quality_tracker.py \\
    --record-event --pr 42 --action closed --merged true \\
    --labels '["agent-generated","agent:ok","agent:debugger"]' \\
    --repo owner/repo

  # Generate weekly report:
  python3 .agent/scripts/quality_tracker.py \\
    --output wiki/agent-scores.md --repo owner/repo

  # Local dry-run report (reads log, no GitHub API):
  python3 .agent/scripts/quality_tracker.py --output -
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent.parent
LOG_FILE   = REPO_ROOT / ".agent" / "pr-quality.jsonl"

QUALITY_LABELS = ["agent:excellent", "agent:ok", "agent:revised", "agent:rejected"]
SCORE_MAP      = {"agent:excellent": 5, "agent:ok": 4, "agent:revised": 2, "agent:rejected": 0}
EMOJI_MAP      = {"agent:excellent": "🌟", "agent:ok": "✅", "agent:revised": "⚠️", "agent:rejected": "❌"}


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def gh_get(path: str, token: str) -> dict | list:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_agent_prs(repo: str, token: str) -> list[dict]:
    """Fetch all closed PRs labelled agent-generated from the GitHub API."""
    prs = []
    page = 1
    while True:
        path = f"/repos/{repo}/pulls?state=closed&labels=agent-generated&per_page=100&page={page}"
        batch = gh_get(path, token)
        if not batch:
            break
        prs.extend(batch)
        page += 1
        if len(batch) < 100:
            break
    return prs


# ---------------------------------------------------------------------------
# Event recording (called by CI on each PR event)
# ---------------------------------------------------------------------------

def record_event(args: argparse.Namespace) -> None:
    try:
        labels = json.loads(args.labels) if args.labels else []
    except json.JSONDecodeError:
        labels = []

    quality = next((l for l in labels if l in QUALITY_LABELS), "")
    agent_name = next((l.removeprefix("agent:") for l in labels
                       if l.startswith("agent:") and l not in QUALITY_LABELS), "unknown")

    event = {
        "ts":       datetime.now(timezone.utc).isoformat(),
        "repo":     args.repo,
        "pr":       args.pr,
        "action":   args.action,
        "merged":   args.merged == "true",
        "agent":    agent_name,
        "quality":  quality,
        "labels":   labels,
    }

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    print(f"Recorded: PR #{args.pr} action={args.action} agent={agent_name} quality={quality or '(none)'}")


# ---------------------------------------------------------------------------
# Report generation (called weekly by agent-feedback.yml)
# ---------------------------------------------------------------------------

def load_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    events = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def build_report(events: list[dict], repo: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Aggregate per agent
    stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "merged": 0, "excellent": 0, "ok": 0,
        "revised": 0, "rejected": 0, "untagged": 0, "score_sum": 0,
    })

    for ev in events:
        if ev.get("action") != "closed":
            continue
        agent = ev.get("agent", "unknown")
        s = stats[agent]
        s["total"] += 1
        if ev.get("merged"):
            s["merged"] += 1
        q = ev.get("quality", "")
        if q in SCORE_MAP:
            s[q.removeprefix("agent:")] += 1
            s["score_sum"] += SCORE_MAP[q]
        else:
            s["untagged"] += 1

    lines = [
        "# Agent Quality Scores",
        "",
        f"> Auto-generated on {today} · source: `{LOG_FILE.relative_to(REPO_ROOT)}`",
        "",
        "## How to read",
        "",
        "| Label | Meaning | Score |",
        "|-------|---------|-------|",
        "| `agent:excellent` 🌟 | Merged as-is, no revisions | 5 |",
        "| `agent:ok` ✅ | Merged after minor revisions | 4 |",
        "| `agent:revised` ⚠️ | Merged after major revisions | 2 |",
        "| `agent:rejected` ❌ | Closed without merging | 0 |",
        "",
        "**Score** = average across tagged PRs. Higher is better.",
        "",
        "---",
        "",
        "## Scores by Agent",
        "",
        "| Agent | PRs | Merged | 🌟 | ✅ | ⚠️ | ❌ | Score |",
        "|-------|-----|--------|----|----|----|----|-------|",
    ]

    for agent, s in sorted(stats.items(), key=lambda x: -(x[1]["score_sum"] / max(x[1]["total"] - x[1]["untagged"], 1))):
        tagged = s["total"] - s["untagged"]
        avg = round(s["score_sum"] / tagged, 1) if tagged > 0 else "—"
        merge_pct = f"{round(s['merged'] / s['total'] * 100)}%" if s["total"] > 0 else "—"
        lines.append(
            f"| `{agent}` | {s['total']} | {merge_pct} "
            f"| {s['excellent']} | {s['ok']} | {s['revised']} | {s['rejected']} | **{avg}** |"
        )

    if not stats:
        lines.append("| _(no data yet)_ | — | — | — | — | — | — | — |")

    total_prs = sum(s["total"] for s in stats.values())
    total_merged = sum(s["merged"] for s in stats.values())
    tagged_prs = sum(s["total"] - s["untagged"] for s in stats.values())

    lines += [
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Total agent PRs tracked**: {total_prs}",
        f"- **Merge rate**: {round(total_merged / total_prs * 100) if total_prs else 0}%",
        f"- **Tagged by reviewer**: {tagged_prs} / {total_prs}",
        "",
        "---",
        "",
        "## Instructions for Reviewers",
        "",
        "When reviewing a PR with the `agent-generated` label:",
        "",
        "1. Review the change as normal",
        "2. Add **one** quality label:",
        "   - `agent:excellent` — merged without significant changes",
        "   - `agent:ok` — merged after small fixes",
        "   - `agent:revised` — merged after major rework",
        "   - `agent:rejected` — closing, agent output unusable",
        "3. The weekly report will update automatically",
        "",
        "> Scores improve the routing system: consistently low-scoring agents",
        "> are flagged for prompt/skill review.",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent quality tracker")
    parser.add_argument("--record-event", action="store_true",
                        help="Record a single PR event to the log")
    parser.add_argument("--pr",     help="PR number")
    parser.add_argument("--action", help="PR action (opened/closed/labeled/...)")
    parser.add_argument("--merged", help="'true' or 'false'")
    parser.add_argument("--labels", help="JSON array of label names")
    parser.add_argument("--repo",   help="owner/repo")
    parser.add_argument("--output", metavar="FILE",
                        help="Write weekly report to FILE (use - for stdout)")
    args = parser.parse_args()

    if args.record_event:
        record_event(args)
        return

    if args.output:
        events = load_log()
        report = build_report(events, repo=args.repo or "")

        if args.output == "-":
            print(report)
        else:
            out = REPO_ROOT / args.output
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report, encoding="utf-8")
            print(f"Report written: {out.relative_to(REPO_ROOT)} ({len(events)} events)")
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
