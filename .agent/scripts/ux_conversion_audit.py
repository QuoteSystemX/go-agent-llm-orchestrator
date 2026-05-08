#!/usr/bin/env python3
"""
UX Conversion & Fitts' Law Auditor
Analyzes HTML/UI structure for interaction efficiency and accessibility.
"""
import sys
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

class UXAuditor:
    def __init__(self, project_path):
        self.project_path = Path(project_path).resolve()
        self.results = []

    def check_fitts_law(self, element):
        """
        Heuristic for Fitts' Law efficiency.
        Checks if clickable elements are large enough.
        """
        # In a real browser audit, we would check CSS/computed styles.
        # Here we check for attributes or class names indicating size.
        classes = element.get("class", [])
        if any(c in str(classes).lower() for c in ["small", "btn-sm", "p-1"]):
            return False, "Element might be too small for efficient interaction (Fitts' Law)"
        return True, "OK"

    def audit_file(self, file_path):
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
        except Exception as e:
            return None

        cta_issues = []
        a11y_issues = []
        
        # 1. Detect CTAs (Buttons and Links)
        ctas = soup.find_all(["button", "a"])
        for cta in ctas:
            # Check Fitts' Law
            passed, msg = self.check_fitts_law(cta)
            if not passed:
                cta_issues.append({"tag": cta.name, "text": cta.get_text().strip(), "issue": msg})
            
            # Check A11y (ARIA labels)
            if not cta.get("aria-label") and not cta.get_text().strip():
                a11y_issues.append({"tag": cta.name, "issue": "Missing aria-label on icon-only action"})

        # 2. Visual Hierarchy (Heading skipping)
        headings = soup.find_all(re.compile(r"^h[1-6]$"))
        prev_level = 0
        for h in headings:
            level = int(h.name[1])
            if level > prev_level + 1 and prev_level != 0:
                a11y_issues.append({"tag": h.name, "issue": f"Heading level skip: H{prev_level} to H{level}"})
            prev_level = level

        return {
            "file": str(file_path.relative_to(self.project_path)),
            "cta_efficiency": len(cta_issues) == 0,
            "cta_issues": cta_issues,
            "a11y_issues": a11y_issues,
            "passed": len(cta_issues) == 0 and len(a11y_issues) == 0
        }

    def run(self):
        # Focus on the dashboard and main UI components
        target_files = list(self.project_path.glob("**/*.html"))
        for f in target_files:
            if "node_modules" not in str(f):
                result = self.audit_file(f)
                if result:
                    self.results.append(result)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    auditor = UXAuditor(path)
    auditor.run()
    
    print(f"\n{'='*60}")
    print(f"🎨 UX CONVERSION & FITTS' LAW AUDIT")
    print(f"{'='*60}")
    
    for res in auditor.results:
        print(f"\n📄 File: {res['file']}")
        if res['passed']:
            print("   ✅ Interaction design is optimal.")
        else:
            for issue in res['cta_issues']:
                print(f"   🔴 CTA Issue: {issue['issue']} ({issue['text']})")
            for issue in res['a11y_issues']:
                print(f"   🟡 A11y Issue: {issue['issue']} ({issue['tag']})")

    # Export for status_report.py
    with open(".agent/bus/ux_metrics.json", "w") as f:
        json.dump({
            "results": auditor.results,
            "passed": all(r["passed"] for r in auditor.results)
        }, f, indent=2)

if __name__ == "__main__":
    main()
