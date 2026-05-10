import os
import json
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
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for file in files:
                if any(file.endswith(ext) for ext in self.code_extensions):
                    rel_path = os.path.relpath(os.path.join(root, file), REPO_ROOT)
                    code_files.append(rel_path)

        if not code_files:
            self.add_metric("coverage", 0, "WARN")
            self.save()
            return

        # Check KIs
        # In this environment, KIs are often in ~/.gemini/antigravity/knowledge
        # But for the project, they might also be in .agent/knowledge if we add them there
        ki_dir = Path("/home/amudrykh/.gemini/antigravity/knowledge")
        covered_files = set()
        
        # Simplified logic: check if KI filename or content mentions a file path
        if ki_dir.exists():
            for ki_file in ki_dir.glob("*.md"):
                content = ki_file.read_text().lower()
                for cf in code_files:
                    if cf.lower() in content:
                        covered_files.add(cf)

        coverage_pct = (len(covered_files) / len(code_files)) * 100
        status = "PASS" if coverage_pct > 50 else "WARN" if coverage_pct > 20 else "FAIL"
        
        self.add_metric("total_files", len(code_files))
        self.add_metric("covered_files", len(covered_files))
        self.add_metric("coverage_pct", f"{coverage_pct:.1f}%", status)
        
        self.save()
        print(f"✅ KI Coverage: {coverage_pct:.1f}% (Status: {status})")

if __name__ == "__main__":
    from pathlib import Path
    KICoverageCollector().run()
