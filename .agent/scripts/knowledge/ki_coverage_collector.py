
# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import os
import json
import sys
from pathlib import Path

try:
    from lib.metrics_base import MetricCollector
    from lib.paths import REPO_ROOT
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from lib.metrics_base import MetricCollector
    from lib.paths import REPO_ROOT

class KICoverageCollector(MetricCollector):
    def __init__(self):
        super().__init__("KI_Coverage")
        self.exclude_dirs = {".agent", ".git", ".claude", ".opencode", "node_modules", "venv", "__pycache__"}
        self.code_extensions = {".py", ".go", ".js", ".ts", ".tsx"}

    def run(self):
        code_files = []
        for root, dirs, files in os.walk(REPO_ROOT):
            # Allow .agent but skip internal heavy dirs
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs or d == ".agent"]
            # But specifically skip .agent internal dirs except scripts
            if ".agent" in root and "scripts" not in root and root != str(REPO_ROOT / ".agent"):
                continue
            
            for file in files:
                if any(file.endswith(ext) for ext in self.code_extensions):
                    rel_path = os.path.relpath(os.path.join(root, file), REPO_ROOT)
                    code_files.append(rel_path)

        if not code_files:
            self.add_metric("coverage", 0, "WARN")
            self.save()
            return

        # Check KIs
        ki_dirs = [
            Path.home() / ".gemini" / "antigravity" / "knowledge",
            REPO_ROOT / ".agent" / "knowledge"
        ]
        covered_files = set()
        
        for ki_dir in ki_dirs:
            if ki_dir.exists():
                for ki_file in ki_dir.glob("*.md"):
                    content = ki_file.read_text().lower()
                    for cf in code_files:
                        if cf.lower() in content:
                            covered_files.add(cf)

        coverage_pct = (len(covered_files) / len(code_files)) * 100
        status = "PASS" if coverage_pct > 50 else "WARN" if coverage_pct > 20 else "FAIL"
        
        uncovered = set(code_files) - covered_files
        if uncovered:
            print("\n⚠️  Uncovered Files:")
            for f in sorted(list(uncovered))[:20]: # Show top 20
                print(f"  - {f}")
            if len(uncovered) > 20:
                print(f"  ... and {len(uncovered) - 20} more.")

        self.add_metric("total_files", len(code_files))
        self.add_metric("covered_files", len(covered_files))
        self.add_metric("coverage_pct", f"{coverage_pct:.1f}%", status)
        
        self.save()
        print(f"\n✅ KI Coverage: {coverage_pct:.1f}% (Status: {status})")

if __name__ == "__main__":
    from pathlib import Path
    KICoverageCollector().run()
