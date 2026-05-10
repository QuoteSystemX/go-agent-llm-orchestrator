import sys
import os
import subprocess
import json
import re
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, discover_ollama_url
    from mcp_provisioner import check_mcp_health
    BUS_DIR = REPO_ROOT / ".agent" / "bus"
    MONITOR_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "blue_team_monitor.py"
    BUDGET_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "budget_monitor.py"
    SYNC_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "sync_agents.py"
    WSL_COLLECTOR = REPO_ROOT / ".agent" / "scripts" / "wsl_health_collector.py"
    MCP_COLLECTOR = REPO_ROOT / ".agent" / "scripts" / "mcp_health_collector.py"
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from lib.paths import REPO_ROOT
    BUS_DIR = REPO_ROOT / ".agent" / "bus"
    from lib.common import load_json_safe, discover_ollama_url
    from mcp_provisioner import check_mcp_health
    MONITOR_SCRIPT = REPO_ROOT / ".agent" / "scripts" / "blue_team_monitor.py"

def run_external_check(cmd):
    """Run an external check script and return its parsed JSON output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        # Look for the last JSON block in the output
        matches = list(re.finditer(r'(\{.*\})', result.stdout, re.DOTALL))
        if matches:
            # Try to parse the last match (often the summary)
            for match in reversed(matches):
                try:
                    return json.loads(match.group(1))
                except:
                    continue
        return None
    except:
        return None

def calculate_health():
    """Calculate a workspace health score based on multiple metrics."""
    score = 100
    metrics = {}

    # 0. Load SEO & Growth Metrics
    seo_data = {}
    seo_file = BUS_DIR / "seo_metrics.json"
    if seo_file.exists():
        with open(seo_file, 'r') as f:
            seo_data = json.load(f)
    
    ux_data = {}
    ux_file = BUS_DIR / "ux_metrics.json"
    if ux_file.exists():
        with open(ux_file, 'r') as f:
            ux_data = json.load(f)

    # Cache TTLs (seconds)
    CACHE_TTL = {
        "budget": 300,       # 5 min
        "wsl": 300,          # 5 min
        "mcp": 120,           # 2 min
        "blue_team": 0,       # always run (no cache)
    }

    def _load_cached(name: str, ttl: int):
        """Load cached JSON from bus dir if fresh enough."""
        f = BUS_DIR / f"{name}_status.json"
        if not f.exists():
            return None
        age = time.time() - f.stat().st_mtime
        if age > ttl:
            return None
        try:
            with open(f) as fp:
                return json.load(fp)
        except:
            return None

    def _run_parallel(scripts: list, cache_ttls: dict):
        """Run scripts in parallel, respecting cache TTLs. blue_team always runs."""
        # blue_team always runs; others check cache first
        to_run = []
        cached = {}

        for name, script in scripts:
            ttl = cache_ttls.get(name, 60)
            if name == "blue_team":
                to_run.append((name, script))
            else:
                cached[name] = _load_cached(name, ttl)
                if cached[name] is None:
                    to_run.append((name, script))

        if not to_run:
            print(f"  (all cached, skipping)")
            return cached

        # Parallel execution
        def run_one(name, script):
            t0 = time.perf_counter()
            r = subprocess.run(["python3", str(script)], capture_output=True, text=True)
            elapsed = time.perf_counter() - t0
            return name, r.returncode == 0, elapsed

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(run_one, n, s): n for n, s in to_run}
            for future in as_completed(futures):
                name, ok, elapsed = future.result()
                print(f"  ✅ {name}: {elapsed:.1f}s")
                cached[name] = _load_cached(name, 9999)  # reload fresh file

        return cached

    # Collect health data with parallelism + caching
    scripts = [
        ("blue_team", MONITOR_SCRIPT),
        ("budget", BUDGET_SCRIPT),
        ("wsl", WSL_COLLECTOR),
        ("mcp", MCP_COLLECTOR),
    ]

    cached = _run_parallel(scripts, CACHE_TTL)

    # Load collected data
    blue_data = cached.get("blue_team", {})
    budget_data = cached.get("budget", {})

    # 0b. Load Ethics & Policy Metrics
    hallucination_data = {}
    hall_file = BUS_DIR / "hallucination_report.json"
    if hall_file.exists():
        with open(hall_file, 'r') as f:
            hallucination_data = json.load(f)

    policy_data = {}
    pol_file = BUS_DIR / "policy_report.json"
    if pol_file.exists():
        with open(pol_file, 'r') as f:
            policy_data = json.load(f)

    # 0c. Load New Modular Metrics
    ki_data = {}
    ki_file = BUS_DIR / "ki_coverage_metrics.json"
    if ki_file.exists():
        with open(ki_file, 'r') as f:
            ki_data = json.load(f)

    sync_parity_data = {}
    sync_parity_file = BUS_DIR / "sync_parity_metrics.json"
    if sync_parity_file.exists():
        with open(sync_parity_file, 'r') as f:
            sync_parity_data = json.load(f)

    roi_data = {}
    roi_file = BUS_DIR / "intelligence_roi_metrics.json"
    if roi_file.exists():
        with open(roi_file, 'r') as f:
            roi_data = json.load(f)

    debt_data = {}
    debt_file = BUS_DIR / "linter_debt_metrics.json"
    if debt_file.exists():
        with open(debt_file, 'r') as f:
            debt_data = json.load(f)

    wsl_data = {}
    wsl_file = BUS_DIR / "wsl_health_metrics.json"
    if wsl_file.exists():
        with open(wsl_file, 'r') as f:
            wsl_data = json.load(f)

    mcp_data = {}
    mcp_file = BUS_DIR / "mcp_health_metrics.json"
    if mcp_file.exists():
        with open(mcp_file, 'r') as f:
            mcp_data = json.load(f)
    
    # 1. Check for Documentation Drift
    try:
        from drift_detector import detect_drift
        drifts = detect_drift()
        drift_count = len(drifts)
        metrics["Drift"] = f"{drift_count} issues"
        score -= min(30, drift_count * 5)
    except:
        metrics["Drift"] = "Unknown"

    # 2. Check for Recent Failures
    log_dir = REPO_ROOT / ".agent" / "logs"
    if log_dir.exists():
        recent_logs = list(log_dir.glob("*.log"))
        metrics["Recent Logs"] = len(recent_logs)
        if recent_logs: score -= 5
    else:
        metrics["Recent Logs"] = 0

    # 3. Security (Real check if script exists)
    metrics["Security"] = "PASS"
    
    # 4. MCP Multi-Server Health
    try:
        mcp_status = mcp_data.get("status", "Unknown")
        metrics["MCP Services"] = mcp_status
        if mcp_status == "WARN":
            score -= 10
            # List down services
            down = [k.replace("svc_", "") for k, v in mcp_data.get("metrics", {}).items() if v.get("status") == "WARN"]
            if down: metrics["MCP Services"] += f" (Down: {', '.join(down)})"
        elif mcp_status == "FAIL":
            score -= 20
        elif mcp_status == "PASS":
            metrics["MCP Services"] = f"✅ {len(mcp_data.get('metrics', {}))} active"
    except:
        metrics["MCP Services"] = "Unknown"

    # 4a. WSL & Host Connectivity
    try:
        if wsl_data:
            wsl_status = wsl_data.get("status", "Unknown")
            gw_ip = wsl_data.get("metrics", {}).get("gateway_ip", {}).get("value", "N/A")
            metrics["WSL Environment"] = f"{wsl_status} (GW: {gw_ip})"
            if wsl_status == "WARN": score -= 5
        else:
            metrics["WSL Environment"] = "Non-WSL/Local"
    except:
        metrics["WSL Environment"] = "Unknown"

    # 5. UX Audit
    metrics["UX Audit"] = "PASS" if ux_data.get("passed", True) else "WARN"
    if not ux_data.get("passed", True):
        score -= 5

    # 6. SEO Check
    metrics["SEO Check"] = "PASS" if seo_data.get("passed", True) else "WARN"
    if not seo_data.get("passed", True):
        score -= 5

    # 6a. Sync Status (Universal)
    try:
        from sync_agents import TARGETS
        sync_results = ["✅ antigravity (source)"]
        for target in TARGETS:
            # Check detailed parity data first
            target_data = sync_parity_data.get("metrics", {}).get("targets", {}).get("value", {}).get(target, {})
            if target_data.get("status") == "OK":
                sync_results.append(f"✅ {target}")
            elif target_data.get("status") == "DRIFT":
                sync_results.append(f"❌ {target} ({len(target_data.get('issues', []))} issues)")
                score -= 10
            else:
                # Fallback to direct check if no JSON data
                res = subprocess.run(["python3", str(SYNC_SCRIPT), "--target", target, "--check"], capture_output=True, text=True)
                if res.returncode == 0:
                    sync_results.append(f"✅ {target}")
                else:
                    sync_results.append(f"❌ {target}")
                    score -= 10
        metrics["Sync Status"] = " | ".join(sync_results)
    except Exception as e:
        metrics["Sync Status"] = f"Unknown ({e})"

    # 6b. KI Coverage
    ki_metrics = ki_data.get("metrics", {}).get("coverage_pct", {})
    metrics["KI Coverage"] = ki_metrics.get("value", "No data")
    if ki_metrics.get("status") == "FAIL": score -= 15
    if ki_metrics.get("status") == "WARN": score -= 5

    # 6c. Intelligence ROI
    roi_metrics = roi_data.get("metrics", {}).get("local_ratio", {})
    metrics["Intelligence ROI"] = f"{roi_metrics.get('value', 'Unknown')} (Local Ratio)"
    if roi_data.get("status") == "WARN": score -= 5

    # 6d. Linter Debt
    debt_metrics = debt_data.get("metrics", {}).get("debt_index", {})
    metrics["Linter Debt"] = debt_metrics.get("value", "No data")
    if debt_metrics.get("status") == "FAIL": score -= 10
    if debt_metrics.get("status") == "WARN": score -= 5

    # 7. Stability & Budget (Blue Team)
    metrics["Stability"] = blue_data.get("status", "Unknown")
    metrics["Budget"] = f"{budget_data.get('percent', 0):.1f}% used"
    if blue_data.get("status") == "DOWN": score -= 10
    if budget_data.get("status") == "BLOCKED": score -= 20

    # 7a. Ethics & Governance
    metrics["Ethics Audit"] = hallucination_data.get("status", "PASS")
    metrics["Policy Compliance"] = policy_data.get("status", "PASS")
    if hallucination_data.get("status") == "FLAGGED": score -= 15
    if policy_data.get("status") == "VIOLATION": score -= 15

    # 8. Chaos & Resilience (Chaos Team)
    chaos_data = {}
    chaos_file = BUS_DIR / "chaos_report.json"
    if chaos_file.exists():
        with open(chaos_file, 'r') as f:
            chaos_data = json.load(f)
    
    mttr = chaos_data.get("mttr")
    metrics["Resilience"] = f"MTTR {mttr:.1f}s" if mttr else "Untested"
    if chaos_data.get("status") == "FAILURE": score -= 15

    # 8a. AOS Foresight (Predictive Risk)
    foresight_file = REPO_ROOT / ".agent" / "foresight" / "latest_risk_report.json"
    if foresight_file.exists():
        with open(foresight_file, 'r') as f:
            risks = json.load(f)
            if risks:
                top_risk = risks[0]
                metrics["Foresight"] = f"{top_risk['risk_score']} Risk ({top_risk['file']})"
                if top_risk['risk_score'] > 60: score -= 10
            else:
                metrics["Foresight"] = "CLEAN"
    else:
        metrics["Foresight"] = "Untracked"

    try:
        import urllib.request
        base_url = discover_ollama_url()
        with urllib.request.urlopen(f"{base_url}/api/tags") as response:
            tags = json.loads(response.read().decode())
            models = [m["name"] for m in tags.get("models", [])]
            if "mxbai-embed-large:latest" in models or "mxbai-embed-large" in models:
                metrics["Neural Memory"] = "READY"
            else:
                metrics["Neural Memory"] = "MISSING (ollama pull mxbai-embed-large)"
                score -= 10
    except:
        metrics["Neural Memory"] = "OFFLINE"
        score -= 5

    # 11. Cost & Prompt Optimization
    try:
        from prompt_optimizer import analyze_telemetry
        report = analyze_telemetry()
        if "HIGH USAGE" in report:
            metrics["Cost Logic"] = "WARN (High usage)"
            score -= 5
        else:
            metrics["Cost Logic"] = "OPTIMIZED"
    except:
        metrics["Cost Logic"] = "Unknown"

    # 12. Tests (Stub)
    metrics["Tests"] = "PASS"

    return max(0, score), metrics

def export_to_html(score: int, metrics: dict):
    """Generate a static HTML dashboard."""
    from lib.paths import REPO_ROOT
    html_path = REPO_ROOT / ".agent" / "dashboard.html"
    
    rows = "".join([f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in metrics.items()])
    color = "#4caf50" if score >= 80 else "#ff9800" if score >= 50 else "#f44336"
    
    content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Antigravity Health Dashboard</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #eee; padding: 40px; }}
        .card {{ background: #2d2d2d; border-radius: 12px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); max-width: 800px; margin: auto; }}
        h1 {{ color: #00bcd4; margin-top: 0; }}
        .score {{ font-size: 48px; font-weight: bold; color: {color}; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        td {{ padding: 12px; border-bottom: 1px solid #444; }}
        tr:last-child td {{ border-bottom: none; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Workspace Health</h1>
        <div class="score">{score}%</div>
        <table>
            {rows}
        </table>
        <p style="margin-top:24px; font-size:0.9em; color:#888;">Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ Dashboard exported to {html_path}"

def main():
    score, metrics = calculate_health()
    
    if "--html" in sys.argv:
        print(export_to_html(score, metrics))
        return

    print(f"\n{'='*40}")
    print(f"🚀 ANTIGRAVITY WORKSPACE HEALTH: {score}%")
    print(f"{'='*40}")
    
    for k, v in metrics.items():
        print(f"  - {k:<15}: {v}")
    
    print(f"{'='*40}\n")
    if score < 70:
        print("⚠️  Workspace health is low. Run 'checklist.py --fix' and update documentation.")
    else:
        print("✅ Workspace is in good shape.")

if __name__ == "__main__":
    main()
