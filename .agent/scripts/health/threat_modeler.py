#!/usr/bin/env python3
"""STRIDE Threat Modeler — LLM-powered git diff security analysis.

Parses staged git diffs, identifies trust boundaries and data-flow risks,
and maps them to STRIDE categories via a local/cloud LLM.

Output: .agent/foresight/threat_model.json
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.llm_client import query_llm_safe

REPO_ROOT = Path(__file__).resolve().parents[3]
FORESIGHT_DIR = REPO_ROOT / ".agent" / "foresight"
THREAT_REPORT = FORESIGHT_DIR / "threat_model.json"

STRIDE_SYSTEM_PROMPT = """You are a senior application security architect performing a STRIDE threat model review.
Analyze the provided git diff and identify security threats.

For each threat, return a JSON array where every element has exactly these keys:
  "threat_type"      : short name of the threat (e.g. "Unvalidated User Input")
  "stride_category"  : one of Spoofing | Tampering | Repudiation | Information Disclosure | Denial of Service | Elevation of Privilege
  "severity"         : one of High | Medium | Low
  "component"        : the affected file or function (e.g. "api/upload.py:handle_upload")
  "description"      : one sentence explaining the risk
  "mitigation"       : one sentence concrete fix recommendation

Return ONLY the JSON array, no prose, no markdown fences."""

REQUIRED_KEYS = {"threat_type", "stride_category", "severity", "component", "description", "mitigation"}
VALID_SEVERITIES = {"High", "Medium", "Low"}
VALID_STRIDE = {
    "Spoofing", "Tampering", "Repudiation",
    "Information Disclosure", "Denial of Service", "Elevation of Privilege",
}


def get_staged_diff() -> str:
    """Return staged diff; falls back to HEAD~1 if nothing is staged."""
    try:
        result = subprocess.run(
            ["git", "diff", "--staged"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        diff = result.stdout.strip()
        if diff:
            return diff
        # Fallback: last commit diff
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception as exc:
        print(f"⚠️  Could not read git diff: {exc}")
        return ""


def parse_diff_to_files(diff: str) -> list[str]:
    """Extract list of changed files from a unified diff."""
    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return files


def _validate_threat(threat: dict) -> bool:
    """Return True if threat dict has all required keys and valid enum values."""
    if not REQUIRED_KEYS.issubset(threat.keys()):
        return False
    if threat.get("severity") not in VALID_SEVERITIES:
        return False
    if threat.get("stride_category") not in VALID_STRIDE:
        return False
    return True


def generate_threat_model(diff: str, files: list[str]) -> list[dict]:
    """Call LLM to produce STRIDE threats; validate and return clean list."""
    file_context = "\n".join(f"  - {f}" for f in files) if files else "  (unknown)"
    prompt = (
        f"Changed files:\n{file_context}\n\n"
        f"Git diff (truncated to 6000 chars):\n{diff[:6000]}"
    )

    response_text, source, _ = query_llm_safe(
        prompt=prompt,
        system_prompt=STRIDE_SYSTEM_PROMPT,
        format_json=True,
    )

    if source == "stub":
        print("⚠️  LLM unavailable — threat_model.json will be empty.")
        return []

    try:
        raw = json.loads(response_text)
        if not isinstance(raw, list):
            # Some models wrap array in {"threats": [...]}
            raw = raw.get("threats", []) if isinstance(raw, dict) else []
    except (json.JSONDecodeError, AttributeError):
        print(f"⚠️  Could not parse LLM response as JSON (source={source}).")
        return []

    threats = [t for t in raw if isinstance(t, dict) and _validate_threat(t)]
    skipped = len(raw) - len(threats)
    if skipped:
        print(f"⚠️  Skipped {skipped} malformed threat(s) (missing keys or invalid enums).")
    return threats


def _get_current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def save_threat_model(threats: list[dict], model_used: str = "qwen2.5-coder:14b") -> None:
    """Persist threat report to .agent/foresight/threat_model.json."""
    FORESIGHT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit": _get_current_commit(),
            "model": model_used,
            "threat_count": len(threats),
        },
        "threats": threats,
    }
    THREAT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    try:
        display = THREAT_REPORT.relative_to(REPO_ROOT)
    except ValueError:
        display = THREAT_REPORT
    print(f"💾 Threat report saved → {display}")


def _print_audit_warning(threats: list[dict]) -> None:
    """Print audit block for High severity threats that have no mitigation."""
    high_threats = [
        t for t in threats
        if t.get("severity") == "High" and not t.get("mitigation", "").strip()
    ]
    if not high_threats:
        return
    print("\n" + "═" * 60)
    print("🚨  SECURITY AUDIT WARNING — Unmitigated High-Severity Threats")
    print("═" * 60)
    for t in high_threats:
        print(f"  [{t['stride_category']}] {t['threat_type']}")
        print(f"    Component : {t['component']}")
        print(f"    Risk      : {t['description']}")
    print("═" * 60)
    print("⛔  Resolve the above before merging.\n")


def _summarize(threats: list[dict]) -> None:
    if not threats:
        print("✅ No security threats identified.")
        return
    by_sev: dict[str, list] = {"High": [], "Medium": [], "Low": []}
    for t in threats:
        by_sev.setdefault(t["severity"], []).append(t)
    print(f"\n🛡️  STRIDE Threat Summary ({len(threats)} threats):")
    for sev in ("High", "Medium", "Low"):
        items = by_sev[sev]
        if items:
            icon = "🔴" if sev == "High" else ("🟠" if sev == "Medium" else "🟡")
            print(f"  {icon} {sev}: {len(items)}")
            for t in items:
                print(f"     [{t['stride_category']}] {t['threat_type']} — {t['component']}")


def analyze(diff: str | None = None) -> list[dict]:
    """Full analysis pipeline. Returns list of validated threat dicts."""
    if diff is None:
        diff = get_staged_diff()

    if not diff:
        print("ℹ️  No staged changes detected — skipping threat analysis.")
        save_threat_model([])
        return []

    files = parse_diff_to_files(diff)
    print(f"🔍 Analyzing {len(files)} changed file(s) for STRIDE threats...")

    threats = generate_threat_model(diff, files)
    save_threat_model(threats)
    _summarize(threats)
    _print_audit_warning(threats)
    return threats


# ── Backward-compat shim ─────────────────────────────────────────────────────

def model_threats(intent: str) -> None:
    """Legacy entry point — now delegates to LLM-powered STRIDE analysis."""
    print(f"🛡️  STRIDE Threat Modeler — analyzing: '{intent}'")
    analyze()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        model_threats(" ".join(sys.argv[1:]))
    else:
        analyze()
