
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
import re
from lib.metrics_base import MetricCollector
from lib.paths import REPO_ROOT

class LinterDebtCollector(MetricCollector):
    def __init__(self):
        super().__init__("Linter_Debt")
        self.exclude_dirs = {".agent", ".git", ".claude", ".opencode", "node_modules", "venv", "__pycache__", "dist"}
        self.code_extensions = {".py", ".go", ".js", ".ts", ".tsx"}
        self.nolint_patterns = [
            re.compile(r"nolint"),
            re.compile(r"noqa"),
            re.compile(r"eslint-disable"),
            re.compile(r"ignore:"),
        ]

    def run(self):
        total_files = 0
        files_with_debt = 0
        total_debt_instances = 0

        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for file in files:
                if any(file.endswith(ext) for ext in self.code_extensions):
                    total_files += 1
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            instances = 0
                            for pattern in self.nolint_patterns:
                                instances += len(pattern.findall(content))
                            
                            if instances > 0:
                                files_with_debt += 1
                                total_debt_instances += instances
                    except:
                        continue

        debt_index = (files_with_debt / total_files * 100) if total_files > 0 else 0
        status = "PASS" if debt_index < 10 else "WARN" if debt_index < 25 else "FAIL"

        self.add_metric("total_files", total_files)
        self.add_metric("files_with_debt", files_with_debt)
        self.add_metric("total_instances", total_debt_instances)
        self.add_metric("debt_index", f"{debt_index:.1f}%", status)

        self.save()
        print(f"✅ Linter Debt Index: {debt_index:.1f}% (Instances: {total_debt_instances})")

if __name__ == "__main__":
    LinterDebtCollector().run()
