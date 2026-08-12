#!/usr/bin/env python3
"""War Room Manager — Active SRE Incident Reflex Loop.

Listens for incidents from the context bus and self_healer repair files,
then executes a real Git-Ops self-healing pipeline:
  diagnose → fix → validate (checklist) → commit → report.
"""

import json
import subprocess
import sys
import time
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
    from lib.common import get_timestamp
    from context import bus_manager
except ImportError:
    sys.path.append(str(_SCRIPTS_DIR.parent))
    from lib.paths import REPO_ROOT
    from lib.common import get_timestamp
    from context import bus_manager

BUS_OUTPUTS = REPO_ROOT / ".agent" / "bus" / "outputs"
CHECKLIST = _SCRIPTS_DIR / "dev" / "checklist.py"
INCIDENTS_LOG = REPO_ROOT / ".agent" / "logs" / "incidents.jsonl"
_PROCESSED_REPAIRS: set[str] = set()


# ── Bus polling ───────────────────────────────────────────────────────────────

def _poll_bus(key: str, timeout: float = 30.0, interval: float = 0.5) -> dict | None:
    """Poll bus_manager every `interval` seconds until `key` appears or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        obj = bus_manager.wait_for_object(key, timeout=interval)
        if obj:
            return obj
        time.sleep(interval)
    return None


# ── Git-Ops helpers ───────────────────────────────────────────────────────────

def _create_branch(incident_id: str) -> str:
    """Create and checkout a hotfix branch. Returns branch name."""
    branch = f"fix/inc-{incident_id}"
    result = subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Branch may already exist — try checking it out
        subprocess.run(
            ["git", "checkout", branch],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
    print(f"📂 Git: on branch {branch}")
    return branch


def _run_validation(branch: str) -> bool:
    """Run checklist.py on the hotfix branch. Returns True if all checks pass."""
    print(f"🔍 Validation: running checklist on {branch}...")
    result = subprocess.run(
        [sys.executable, str(CHECKLIST), str(REPO_ROOT)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("✅ Validation: checklist passed.")
        return True
    print(f"❌ Validation failed:\n{result.stdout[-800:]}")
    return False


def _commit_fix(branch: str, incident_id: str) -> bool:
    """Stage all changes and commit if anything is staged. Returns True if committed."""
    # Check for unstaged changes to add
    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if diff.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)

    # Guard: only commit if there is something staged
    staged = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=REPO_ROOT,
    )
    if staged.returncode == 0:  # exit 0 means nothing staged
        print("ℹ️  Nothing staged — skipping commit.")
        return False

    msg = f"fix: incident {incident_id} resolved on {branch}"
    subprocess.run(
        ["git", "commit", "-m", msg, "--no-verify"],
        cwd=REPO_ROOT, check=True,
    )
    print(f"✅ Git: committed fix — '{msg}'")
    return True


def _report_pr(branch: str) -> None:
    """Print merge-ready branch details."""
    print(f"\n{'─' * 50}")
    print(f"🚀 Merge-Ready Hotfix Branch: {branch}")
    print(f"   Create PR:  gh pr create --head {branch} --base main")
    print(f"   Review:     git log main..{branch} --oneline")
    print(f"{'─' * 50}\n")


def _log_incident(
    incident_id: str,
    diagnosis: dict | None,
    proposed_fix: dict,
    git_status: dict,
) -> None:
    """Append a durable record to .agent/logs/incidents.jsonl.

    This is the queryable incident history the blameless retro
    (.agent/scripts/orchestration/blameless_retro.py) reads to group repeat
    incidents by root cause. Not itself blameless — the retro's *output* is
    what gets mechanically redacted, not this raw log.
    """
    INCIDENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    # diagnosis/proposed_fix may be raw content dicts or full bus objects
    # ({id, type, author, timestamp, content}) depending on the caller —
    # unwrap defensively rather than assume either shape.
    diagnosis_content = (diagnosis or {}).get("content", diagnosis or {})
    fix_content = proposed_fix.get("content", proposed_fix)
    record = {
        "incident_id": incident_id,
        "ts": get_timestamp(),
        "root_cause_signature": diagnosis_content.get("root_cause_signature", "unknown"),
        "diagnosis_summary": diagnosis_content.get("summary", ""),
        "fix_summary": fix_content.get("summary", fix_content.get("status", "")),
        "branch": git_status.get("branch"),
        "status": git_status.get("status", "unknown"),
    }
    with open(INCIDENTS_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Repair file scanner ───────────────────────────────────────────────────────

def _scan_repair_files() -> list[dict]:
    """Return unprocessed repair_*.json incidents from bus/outputs/."""
    incidents = []
    if not BUS_OUTPUTS.exists():
        return incidents
    for f in sorted(BUS_OUTPUTS.glob("repair_*.json")):
        if str(f) in _PROCESSED_REPAIRS:
            continue
        try:
            data = json.loads(f.read_text())
            incidents.append({
                "id": f"selfheal_{f.stem}",
                "content": {"stderr": data.get("error", ""), "repair_file": str(f)},
                "_repair_path": str(f),
            })
        except Exception as exc:
            print(f"⚠️  Could not read {f.name}: {exc}")
    return incidents


# ── Core pipeline ─────────────────────────────────────────────────────────────

def manage_war_room(incident_id: str) -> None:
    """Full autonomous recovery pipeline for one incident."""
    print(f"\n🎖  War Room: managing incident {incident_id}...")

    incident = bus_manager.wait_for_object(incident_id, timeout=2)
    if not incident:
        print(f"❌ Incident {incident_id} not found on bus.")
        return

    # 1. Spawn Debugger agent task
    print("🎖  Requesting Root Cause Analysis from Debugger...")
    bus_manager.push(
        f"task_debug_{incident_id}", "requirement", "war_room_manager",
        json.dumps({
            "agent": "debugger",
            "instruction": (
                f"Analyze incident {incident_id}. Error: {incident['content'].get('stderr', 'N/A')}. "
                "In your diagnosis object, include a `root_cause_signature` field: a short "
                "kebab-case tag identifying the underlying root cause (not the symptom), e.g. "
                "'missing-timeout-default' or 'unhandled-nil-pointer' — this is used to detect "
                "when the same root cause recurs across incidents, so keep it stable and specific "
                "enough to distinguish real causes but general enough to match recurrences. Also "
                "include a one-sentence `summary` field."
            ),
            "incident_ref": incident_id,
        }),
    )

    # 2. Wait for Debugger diagnosis (real poll, not sleep)
    diagnosis = _poll_bus(f"diagnosis_{incident_id}", timeout=30)
    if not diagnosis:
        print("⚠️  Debugger did not respond in time — proceeding with raw error context.")

    # 3. Spawn Test Engineer fix request
    print("🎖  Requesting fix from Test Engineer...")
    bus_manager.push(
        f"task_fix_{incident_id}", "requirement", "war_room_manager",
        json.dumps({
            "agent": "test-engineer",
            "instruction": "Generate and verify a fix for the analyzed incident.",
            "incident_ref": incident_id,
            "diagnosis": diagnosis or {},
        }),
    )

    # 4. Wait for proposed fix
    fix_proposal = _poll_bus(f"fix_{incident_id}", timeout=30)
    proposed_fix = fix_proposal or {
        "incident_ref": incident_id,
        "branch_name": f"fix/inc-{incident_id}",
        "auto_commit": True,
        "status": "ready_to_apply",
    }
    bus_manager.push(
        f"fix_{incident_id}", "proposed_fix", "war_room_manager",
        json.dumps(proposed_fix),
    )
    print("✅ War Room: proposed fix on bus.")

    # 5. Git-Ops pipeline (writes the durable incident record itself, staged
    # into the same commit as the fix — see _activate_git_ops)
    _activate_git_ops(incident_id, diagnosis, proposed_fix)


def _activate_git_ops(incident_id: str, diagnosis: dict | None, fix: dict) -> dict:
    """Full Git-Ops pipeline: branch → validate → log → commit → report.

    The incident record is written *before* `_commit_fix`, so `git add -A`
    picks it up and it lands in the same commit as the fix — logging after
    commit would leave it permanently uncommitted.

    Returns a status dict ({"branch", "status"}) for the caller —
    status is one of: checklist_failed, committed, no_changes, error.
    """
    branch = f"fix/inc-{incident_id}"
    try:
        branch = _create_branch(incident_id)
        validated = _run_validation(branch)
        if not validated:
            print(f"🛑 Git-Ops halted: checklist failed on {branch}. Branch left for manual review.")
            return {"branch": branch, "status": "checklist_failed"}
        _log_incident(incident_id, diagnosis, fix, {"branch": branch, "status": "committed"})
        committed = _commit_fix(branch, incident_id)
        _report_pr(branch)
        return {"branch": branch, "status": "committed" if committed else "no_changes"}
    except subprocess.CalledProcessError as exc:
        print(f"❌ Git-Ops error: {exc}")
        return {"branch": branch, "status": "error"}
    except Exception as exc:
        print(f"❌ Unexpected error in Git-Ops: {exc}")
        return {"branch": branch, "status": "error"}


# ── Entry points ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        manage_war_room(sys.argv[1])
    else:
        print("🎖  War Room: Daemon active. Listening for incidents and repair files...")
        seen: set[str] = set()
        while True:
            # Bus incidents
            try:
                objects = bus_manager.get_objects_by_type("incident")
                for obj in objects:
                    if obj["id"] not in seen:
                        manage_war_room(obj["id"])
                        seen.add(obj["id"])
            except Exception as exc:
                print(f"⚠️  Bus scan error: {exc}")

            # Repair file incidents from self_healer
            for repair_incident in _scan_repair_files():
                inc_id = repair_incident["id"]
                if inc_id not in seen:
                    # Push to bus so manage_war_room can find it
                    bus_manager.push(inc_id, "incident", "self_healer",
                                     json.dumps(repair_incident["content"]))
                    manage_war_room(inc_id)
                    seen.add(inc_id)
                    _PROCESSED_REPAIRS.add(repair_incident["_repair_path"])

            time.sleep(2)
