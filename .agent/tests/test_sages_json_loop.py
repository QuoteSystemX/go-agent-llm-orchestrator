#!/usr/bin/env python3
import sys
import json
from pathlib import Path

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Import schemas using dynamic package structure
def _load_schemas():
    try:
        orchestration = __import__("orchestration.sages_schemas", fromlist=["CritiqueList", "VerdictList"])
        return orchestration.CritiqueList, orchestration.VerdictList
    except ImportError:
        sys.path.insert(0, str(SCRIPTS_DIR / "orchestration"))
        sages_schemas = __import__("sages_schemas", fromlist=["CritiqueList", "VerdictList"])
        return sages_schemas.CritiqueList, sages_schemas.VerdictList

CritiqueList, VerdictList = _load_schemas()

def validate_verdict_resolutions(critique_list: CritiqueList, verdict_list: VerdictList) -> tuple[bool, str]:
    """
    Automated validation step to verify that the Proposer has responded
    to every 'blocker' severity critique point with an 'accepted: true' resolution.
    """
    critique_map = {c.id: c for c in critique_list.critiques}
    resolutions_map = {r.critique_id: r for r in verdict_list.resolutions}

    # Verify that every blocker critique is accepted
    for c_id, c in critique_map.items():
        if c.severity == "blocker":
            res = resolutions_map.get(c_id)
            if not res:
                return False, f"Missing resolution for blocker critique: {c_id}"
            if not res.accepted:
                return False, f"Blocker critique {c_id} was rejected or not accepted: '{res.resolution}'"

    return True, "All blocker critiques successfully accepted and resolved."

def test_json_loop_schemas():
    print("🧪 Running JSON Feedback Loop schema and logic tests...")

    # Case 1: Valid critiques JSON
    crit_json = """{
        "critiques": [
            {"id": "CRIT-01", "category": "security", "severity": "blocker", "description": "SQL Injection found", "suggested_action": "Use parameterized query"},
            {"id": "CRIT-02", "category": "performance", "severity": "warning", "description": "Missing index", "suggested_action": "Add index on user_id"}
        ]
    }"""
    crit_data = json.loads(crit_json)
    crit_list = CritiqueList.from_dict(crit_data)
    assert len(crit_list.critiques) == 2
    assert crit_list.critiques[0].id == "CRIT-01"
    assert crit_list.critiques[0].severity == "blocker"

    # Case 2: Proposer accepts blocker
    verd_json_ok = """{
        "resolutions": [
            {"critique_id": "CRIT-01", "accepted": true, "resolution": "Applied pgx parameterized queries"},
            {"critique_id": "CRIT-02", "accepted": false, "resolution": "Skipped because table is small"}
        ]
    }"""
    verd_data_ok = json.loads(verd_json_ok)
    verd_list_ok = VerdictList.from_dict(verd_data_ok)
    
    ok, msg = validate_verdict_resolutions(crit_list, verd_list_ok)
    print(f"Accepted blocker validation: {ok} ➔ '{msg}'")
    assert ok is True, f"Expected validation to pass, got error: {msg}"

    # Case 3: Proposer rejects blocker (must fail validation!)
    verd_json_fail = """{
        "resolutions": [
            {"critique_id": "CRIT-01", "accepted": false, "resolution": "No, string interpolation is fine"},
            {"critique_id": "CRIT-02", "accepted": true, "resolution": "Added index"}
        ]
    }"""
    verd_data_fail = json.loads(verd_json_fail)
    verd_list_fail = VerdictList.from_dict(verd_data_fail)
    
    ok_fail, msg_fail = validate_verdict_resolutions(crit_list, verd_list_fail)
    print(f"Rejected blocker validation (should fail): {ok_fail} ➔ '{msg_fail}'")
    assert ok_fail is False, "Expected validation to fail because a blocker was rejected"
    assert "was rejected" in msg_fail

    # Case 4: Invalid Critique parsing (type mismatch)
    bad_crit_json = """{
        "critiques": [
            {"id": "CRIT-01", "category": "invalid-cat", "severity": "blocker", "description": "", "suggested_action": ""}
        ]
    }"""
    try:
        CritiqueList.from_dict(json.loads(bad_crit_json))
        assert False, "Expected AssertionError due to invalid category"
    except AssertionError as e:
        print(f"Caught expected assertion error: {e}")

    print("✅ All JSON Feedback Loop schema and logic tests passed successfully!")

if __name__ == "__main__":
    test_json_loop_schemas()
