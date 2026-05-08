import json
from pathlib import Path

def generate_sprint_advice():
    repo_root = Path(__file__).resolve().parents[2]
    foresight_file = repo_root / ".agent" / "foresight" / "latest_risk_report.json"
    
    print("📋 AOS Sprint Advisor: Strategic Recommendations")
    
    if not foresight_file.exists():
        print("  ❌ No foresight report found. Run entropy_analyzer.py first.")
        return

    risks = json.loads(foresight_file.read_text())
    critical_risks = [r for r in risks if r["risk_score"] > 50]
    
    if not critical_risks:
        print("  ✅ All systems stable. Focus on new features.")
        return

    print(f"\n  ⚠️  DETECTED {len(critical_risks)} DEGRADATION RISKS")
    print("  -------------------------------------------")
    
    for r in critical_risks[:3]:
        print(f"  [STORY] Refactor {r['file']}")
        print(f"    - Reason: Risk Score {r['risk_score']} (Complexity: {r['complexity']}, Churn: {r['churn']})")
        if r.get("trend", 0) > 0:
            print(f"    - Trend: Increasing (+{r['trend']})")
        print("    - Goal: Reduce indentation depth and split logic into sub-modules.")
        print()

    print("  Recommendation: Include at least one REFACTOR task in the next sprint.")

if __name__ == "__main__":
    generate_sprint_advice()
