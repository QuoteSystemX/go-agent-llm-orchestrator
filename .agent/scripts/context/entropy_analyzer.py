
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
import subprocess
import json
from pathlib import Path

def get_file_complexity(path):
    """Simple complexity proxy based on line count and indentation depth."""
    try:
        lines = path.read_text().splitlines()
        line_count = len(lines)
        max_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip())
            if indent > max_indent:
                max_indent = indent
        
        # Heuristic: deep indentation + many lines = high complexity
        return (line_count * 0.1) + (max_indent * 0.5)
    except Exception:
        return 0

def get_churn_metrics():
    """Get git churn (number of times a file was modified)."""
    try:
        cmd = ["git", "log", "--name-only", "--pretty=format:"]
        output = subprocess.check_output(cmd).decode("utf-8")
        files = [f for f in output.split("\n") if f.strip()]
        churn = {}
        for f in files:
            churn[f] = churn.get(f, 0) + 1
        return churn
    except Exception:
        return {}

def run_foresight_analysis(repo_root=None):
    print("🔭 Starting AOS Foresight Analysis...")
    if not repo_root:
        try:
            from lib.paths import REPO_ROOT
            repo_root = REPO_ROOT
        except ImportError:
            repo_root = Path(__file__).resolve().parents[3]
    
    repo_root = Path(repo_root)
    monitored_exts = [".py", ".ts", ".tsx", ".go", ".js"]
    
    churn = get_churn_metrics()
    report = []
    
    # Load history for trend analysis
    history_file = repo_root / ".agent" / "foresight" / "complexity_history.json"
    history = {}
    if history_file.exists():
        try: history = json.loads(history_file.read_text())
        except Exception: pass

    abs_root = repo_root.resolve()
    for ext in monitored_exts:
        for file in repo_root.glob(f"**/*{ext}"):
            abs_file = file.resolve()
            
            # Prevent path traversal outside the repository root
            if not str(abs_file).startswith(str(abs_root)):
                continue
                
            try:
                rel_path = str(abs_file.relative_to(abs_root))
            except ValueError as e:
                # Log relative path calculation error if it fails
                print(f"⚠️ Warning: Failed to calculate relative path for {file}: {e}", file=sys.stderr)
                continue
            
            # Skip ignored directories (auxiliary, archived, scratch, and config folders)
            ignored_dirs = {".agent", "node_modules", "dist", "archive", "scratch", ".claude", ".opencode"}
            if any(part in ignored_dirs for part in Path(rel_path).parts):
                continue
                
            complexity = get_file_complexity(file)
            file_churn = churn.get(rel_path, 0)
            
            # Trend calculation
            prev_complexity = history.get(rel_path, complexity)
            trend = complexity - prev_complexity
            
            # Risk score: (Churn * 0.4) + (Complexity * 0.4) + (Trend * 0.2)
            risk_score = (file_churn * 0.4) + (complexity * 0.4) + (max(0, trend) * 5.0)
            
            report.append({
                "file": rel_path,
                "complexity": round(complexity, 2),
                "trend": round(trend, 2),
                "churn": file_churn,
                "risk_score": round(risk_score, 2)
            })
            
            # Update history
            history[rel_path] = complexity
    
    # Save history and report
    foresight_dir = repo_root / ".agent" / "foresight"
    foresight_dir.mkdir(parents=True, exist_ok=True)
    history_file.write_text(json.dumps(history, indent=2))
    
    report.sort(key=lambda x: x["risk_score"], reverse=True)
    (foresight_dir / "latest_risk_report.json").write_text(json.dumps(report, indent=2))
    
    print("\n⚠️  TOP ARCHITECTURAL RISKS (Predictive Degradation):")
    for r in report[:5]:
        status = "🔴 CRITICAL" if r["risk_score"] > 50 else "🟡 WARNING"
        trend_str = f" (📈 +{r['trend']})" if r["trend"] > 0 else ""
        print(f"  - {status}: {r['file']} (Risk: {r['risk_score']}){trend_str}")
    
    if not report:
        print("✅ No high risks detected in current codebase.")

    return report

if __name__ == "__main__":
    run_foresight_analysis()
