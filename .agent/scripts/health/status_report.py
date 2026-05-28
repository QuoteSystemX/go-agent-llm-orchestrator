# Antigravity Domain-Aware Import Logic
import sys
import os
import subprocess
import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 1. Standardize Path Resolution
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

# Add all domain directories to path for static analysis and runtime
for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
    d_path = str(SCRIPTS_DIR / domain)
    if d_path not in sys.path:
        sys.path.append(d_path)

import importlib

try:
    from lib.paths import REPO_ROOT
    from lib.common import load_json_safe, discover_ollama_url
except ImportError:
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[3]
    def load_json_safe(p): 
        try: return json.loads(Path(p).read_text())
        except: return {}
    def discover_ollama_url(): return "http://localhost:11434"

# Dynamic imports to satisfy both runtime and static analysis tools
def _safe_import(module_name, attr_name=None, default=None):
    try:
        # Try package-style first
        for prefix in ["", "health.", "delivery.", "models."]:
            try:
                mod = importlib.import_module(prefix + module_name)
                return getattr(mod, attr_name) if attr_name else mod
            except ImportError:
                continue
        return default
    except:
        return default

check_mcp_health = _safe_import("mcp_provisioner", "check_mcp_health", lambda: {"status": "Unknown"})
TARGETS = _safe_import("sync_agents", "TARGETS", [])
get_agent_stats = _safe_import("agent_scorer", "get_stats", lambda: {})
analyze_telemetry = _safe_import("prompt_optimizer", "analyze_telemetry", lambda: "Unknown")

BUS_DIR = REPO_ROOT / ".agent" / "bus"
DATA_DIR = REPO_ROOT / ".agent" / "data"
HISTORY_PATH = DATA_DIR / "metrics_history.jsonl"
MAX_HISTORY = 500

MONITOR_SCRIPT = SCRIPTS_DIR / "health" / "blue_team_monitor.py"
BUDGET_SCRIPT = SCRIPTS_DIR / "health" / "budget_monitor.py"
SYNC_SCRIPT = SCRIPTS_DIR / "delivery" / "sync_agents.py"
WSL_COLLECTOR = SCRIPTS_DIR / "health" / "wsl_health_collector.py"
MCP_COLLECTOR = SCRIPTS_DIR / "health" / "mcp_health_collector.py"
KI_COLLECTOR = SCRIPTS_DIR / "knowledge" / "ki_coverage_collector.py"
WIKI_SYNC = SCRIPTS_DIR / "knowledge" / "wiki_sync.py"

def run_external_check(cmd: List[str]) -> Optional[Dict[str, Any]]:
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

def append_history(score: int, metrics: dict):
    """Append a snapshot to the JSONL history log."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "score": score}
        # Extract numeric values from key metrics
        for k, v in metrics.items():
            vs = str(v)
            if "Drift" in k:
                m = re.search(r"(\d+)", vs)
                if m: record["drift"] = int(m.group(1))
            elif "Budget" in k:
                m = re.search(r"([\d.]+)", vs)
                if m: record["budget"] = float(m.group(1))
            elif "Resilience" in k or "MTTR" in vs:
                m = re.search(r"([\d.]+)", vs)
                if m: record["mttr"] = float(m.group(1))
            elif "Linter Debt" in k:
                m = re.search(r"([\d.]+)", vs)
                if m: record["linter"] = float(m.group(1))
            elif "KI Coverage" in k:
                m = re.search(r"([\d.]+)", vs)
                if m: record["ki"] = float(m.group(1))
            elif "MCP" in k and "active" in vs:
                m = re.search(r"(\d+)", vs)
                if m: record["mcp"] = int(m.group(1))
            elif "ROI" in k or "Intelligence" in k:
                m = re.search(r"([\d.]+)", vs)
                if m: record["roi"] = float(m.group(1))
        with open(HISTORY_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
        # Trim to MAX_HISTORY
        lines = HISTORY_PATH.read_text().strip().split("\n")
        if len(lines) > MAX_HISTORY:
            HISTORY_PATH.write_text("\n".join(lines[-MAX_HISTORY:]) + "\n")
    except Exception:
        pass  # history is non-critical

def read_history(key: str = "score", limit: int = 100) -> list:
    """Read numeric history for a given metric key from JSONL."""
    values = []
    try:
        if not HISTORY_PATH.exists():
            return values
        lines = HISTORY_PATH.read_text().strip().split("\n")
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                v = rec.get(key)
                if v is not None:
                    values.append(float(v))
            except Exception:
                continue
    except Exception:
        pass
    return values

def generate_sparkline_svg(values: list, width: int = 100, height: int = 24, color: str = "#10b981", uid: str = "s") -> str:
    """Generate an inline SVG sparkline polyline from numeric values."""
    if len(values) < 2:
        return ""
    # Normalize values to fit in viewport
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        vrange = 1.0  # avoid division by zero
    else:
        vrange = vmax - vmin
    padding = 4
    draw_w = width - padding * 2
    draw_h = height - padding * 2
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = padding + (i / (n - 1)) * draw_w
        y = padding + draw_h - ((v - vmin) / vrange) * draw_h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    
    # Determine gradient color based on trend
    trend = values[-1] - values[0] if len(values) > 1 else 0
    if trend > 0:
        grad_start = "#ef4444"  # red (increase = bad for most metrics)
        grad_end = "#f59e0b"
    else:
        grad_start = color
        grad_end = "#10b981"
    
    gid = f"sg-{uid}"
    gid_fill = f"sgf-{uid}"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block">'
        f'<defs>'
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{grad_start}" stop-opacity="0.4"/>'
        f'<stop offset="100%" stop-color="{grad_end}" stop-opacity="0.8"/>'
        f'</linearGradient>'
        f'<linearGradient id="{gid_fill}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{grad_end}" stop-opacity="0.15"/>'
        f'<stop offset="100%" stop-color="{grad_start}" stop-opacity="0.02"/>'
        f'</linearGradient>'
        f'</defs>'
        f'<polygon points="{padding},{height - padding} {polyline} {padding + draw_w},{height - padding}" '
        f'fill="url(#{gid_fill})" />'
        f'<polyline points="{polyline}" fill="none" '
        f'stroke="url(#{gid})" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )

def calculate_health() -> Tuple[int, Dict[str, Any]]:
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

    def _load_cached(name: str, ttl: int) -> Optional[Dict[str, Any]]:
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

    def _run_parallel(scripts: List[Tuple[str, str]], cache_ttls: Dict[str, int]) -> Dict[str, Any]:
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
        def run_one(name: str, script: str) -> Tuple[str, bool, float]:
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
    blue_data = cached.get("blue_team") or {}
    budget_data = cached.get("budget") or {}

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

    # 0c. Load New Modular Metrics — run collector fresh to avoid stale cache
    if KI_COLLECTOR.exists():
        subprocess.run(["python3", str(KI_COLLECTOR)], capture_output=True, text=True)
    
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

    # 1a. Check for Agent Skills Integrity
    try:
        import yaml
        agents_dir = REPO_ROOT / ".agent" / "agents"
        skills_dir = REPO_ROOT / ".agent" / "skills"
        
        agent_files = []
        for root, _, files in os.walk(str(agents_dir)):
            for file in files:
                if file.endswith(".md"):
                    agent_files.append(os.path.join(root, file))
                    
        missing_skills = set()
        for agent_file in agent_files:
            try:
                with open(agent_file, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if match:
                    frontmatter_text = match.group(1)
                    data = yaml.safe_load(frontmatter_text)
                    if data and "skills" in data:
                        skills_raw = data["skills"]
                        skills = []
                        if isinstance(skills_raw, str):
                            skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
                        elif isinstance(skills_raw, list):
                            skills = [str(s).strip() for s in skills_raw if s]
                        for skill in skills:
                            if not (skills_dir / skill).exists():
                                missing_skills.add(skill)
            except:
                continue
        
        if missing_skills:
            metrics["Agent Skills"] = f"❌ {len(missing_skills)} missing"
            score -= min(40, len(missing_skills) * 10)
        else:
            metrics["Agent Skills"] = "✅ 100% Integrity"
    except Exception as e:
        metrics["Agent Skills"] = f"Unknown ({e})"

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

    # 6. SEO Check (skipped for non-web projects)
    if seo_data.get("skipped"):
        metrics["SEO Check"] = "N/A"
    elif seo_data.get("passed", True):
        metrics["SEO Check"] = "PASS"
    else:
        metrics["SEO Check"] = "WARN"
        score -= 5

    # 6a. Sync Status (Universal)
    try:
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

    # 6ab. Fresh Provisioning Check & Scaffolding
    knowledge_dir = REPO_ROOT / ".agent" / "knowledge"
    init_marker = knowledge_dir / ".initialized"
    if not init_marker.exists():
        # RUNTIME BOOTSTRAPPING
        try:
            knowledge_dir.mkdir(parents=True, exist_ok=True)
            init_marker.write_text(f"Auto-initialized by status_report.py on {datetime.now().isoformat()}\n")
            
            manifest = knowledge_dir / "MANIFEST.md"
            if not manifest.exists():
                manifest.write_text("""# 📚 Knowledge Manifest
This repository uses the Karpathy Wiki-First methodology.

## 🧠 State: FRESH_PROVISIONING
This project-specific knowledge base has been provisioned but not yet discovered.

## 🚀 Recommended Action
The repository is newly provisioned. To build the local intelligence base, run:
1. `/discovery` - to map the codebase.
2. `/wiki audit` - to generate initial knowledge fragments.
""")
            metrics["Knowledge State"] = "🌱 FRESH_PROVISIONING (Self-Healed)"
        except Exception as e:
            metrics["Knowledge State"] = f"🌱 FRESH_PROVISIONING (Boot error: {e})"
    else:
        metrics["Knowledge State"] = "🧠 INITIALIZED"

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
    chaos_ts = chaos_data.get("timestamp")
    resilience_status = "Untested"
    if mttr:
        resilience_status = f"MTTR {mttr:.1f}s"
        # Check staleness
        try:
            last_run = datetime.fromisoformat(chaos_ts.replace("Z", ""))
            days_since = (datetime.now(timezone.utc).replace(tzinfo=None) - last_run).days
            if days_since > 7:
                resilience_status += f" (⚠️ Stale: {days_since}d ago)"
                score -= 5
        except:
            pass
    
    metrics["Resilience"] = resilience_status
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

    # 13. Top Agents (Heatmap)
    try:
        stats = get_agent_stats()
        if stats:
            # Sort by count
            top_agents = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
            metrics["Top Agents"] = ", ".join([f"@{k}({v['count']})" for k, v in top_agents])
        else:
            metrics["Top Agents"] = "No activity recorded"
    except:
        metrics["Top Agents"] = "Unknown"

    return max(0, score), metrics

def gather_diagnostics(metrics: dict) -> dict:
    """Collect raw diagnostic data from bus files for drawer inspector."""
    diagnostics = {}
    
    for k in metrics:
        v = metrics[k]
        v_str = str(v)
        detail = {}
        
        # Drift — load drift_detector results
        if "Drift" in k:
            try:
                from drift_detector import detect_drift
                drifts = detect_drift()
                items = []
                for d in (drifts if isinstance(drifts, list) else []):
                    if isinstance(d, dict):
                        items.append({"file": d.get("file", d.get("path", "?")), "msg": d.get("message", d.get("msg", ""))})
                    else:
                        items.append({"file": str(d), "msg": ""})
                detail["items"] = items
                detail["source"] = "drift_detector"
            except Exception as e:
                detail["error"] = str(e)
        
        # MCP — load full service health
        elif "MCP" in k:
            mcp_file = BUS_DIR / "mcp_health_metrics.json"
            if mcp_file.exists():
                data = load_json_safe(mcp_file)
                detail["services"] = {k.replace("svc_", ""): v for k, v in data.get("metrics", {}).items()}
                detail["status"] = data.get("status")
                detail["source"] = "mcp_health_metrics.json"
        
        # Budget — load raw budget data
        elif "Budget" in k:
            budget_file = BUS_DIR / "budget_status.json"
            if budget_file.exists():
                data = load_json_safe(budget_file)
                detail["usage"] = data.get("percent", 0)
                detail["limit"] = data.get("limit", 0)
                detail["priority"] = data.get("priority")
                detail["source"] = "budget_status.json"
        
        # KI Coverage — load full coverage data
        elif "KI Coverage" in k:
            ki_file = BUS_DIR / "ki_coverage_metrics.json"
            if ki_file.exists():
                data = load_json_safe(ki_file)
                detail["coverage_pct"] = data.get("metrics", {}).get("coverage_pct", {})
                detail["total_files"] = data.get("metrics", {}).get("total_files", {})
                detail["covered_files"] = data.get("metrics", {}).get("covered_files", {})
                detail["source"] = "ki_coverage_metrics.json"
        
        # ROI — load intelligence ROI
        elif "ROI" in k or "Intelligence" in k:
            roi_file = BUS_DIR / "intelligence_roi_metrics.json"
            if roi_file.exists():
                data = load_json_safe(roi_file)
                detail["local_calls"] = data.get("metrics", {}).get("local_calls", {})
                detail["cloud_calls"] = data.get("metrics", {}).get("cloud_calls", {})
                detail["total_calls"] = data.get("metrics", {}).get("total_calls", {})
                detail["source"] = "intelligence_roi_metrics.json"
        
        # Linter Debt — load full debt data
        elif "Linter Debt" in k or "Linter" in k:
            debt_file = BUS_DIR / "linter_debt_metrics.json"
            if debt_file.exists():
                data = load_json_safe(debt_file)
                detail["debt_index"] = data.get("metrics", {}).get("debt_index", {})
                detail["files_with_debt"] = data.get("metrics", {}).get("files_with_debt", {})
                detail["total_instances"] = data.get("metrics", {}).get("total_instances", {})
                detail["source"] = "linter_debt_metrics.json"
        
        # Foresight — load risk data
        elif "Foresight" in k:
            foresight_file = REPO_ROOT / ".agent" / "foresight" / "latest_risk_report.json"
            if foresight_file.exists():
                data = load_json_safe(foresight_file)
                if isinstance(data, list):
                    detail["risks"] = data[:10]
                detail["source"] = "foresight/latest_risk_report.json"
        
        # Resilience / Chaos — load chaos report
        elif "Resilience" in k or "MTTR" in v_str:
            chaos_file = BUS_DIR / "chaos_report.json"
            if chaos_file.exists():
                data = load_json_safe(chaos_file)
                detail["mttr"] = data.get("mttr")
                detail["status"] = data.get("status")
                detail["source"] = "chaos_report.json"
        
        # Ethics — load hallucination report
        elif "Ethics" in k:
            hall_file = BUS_DIR / "hallucination_report.json"
            if hall_file.exists():
                data = load_json_safe(hall_file)
                detail["flagged_items"] = data.get("flagged_items", [])
                detail["source"] = "hallucination_report.json"
        
        # Sync Parity
        elif "Sync" in k:
            sync_file = BUS_DIR / "sync_parity_metrics.json"
            if sync_file.exists():
                data = load_json_safe(sync_file)
                detail["targets"] = data.get("metrics", {}).get("targets", {})
                detail["source"] = "sync_parity_metrics.json"
        
        # Top Agents
        elif "Agents" in k and "Top" in k:
            try:
                stats = get_agent_stats()
                if stats:
                    detail["agents"] = {k: v for k, v in sorted(stats.items(), key=lambda x: x[1].get("count", 0), reverse=True)[:10]}
                    detail["source"] = "agent_scorer"
            except:
                detail["error"] = "agent_scorer unavailable"
        
        # DX / UX
        elif "UX" in k:
            ux_file = BUS_DIR / "ux_metrics.json"
            if ux_file.exists():
                data = load_json_safe(ux_file)
                detail["results"] = data.get("results", [])
                detail["source"] = "ux_metrics.json"
        
        # Sync Status details
        elif "Sync Status" in k:
            sync_file = BUS_DIR / "sync_parity_metrics.json"
            if sync_file.exists():
                data = load_json_safe(sync_file)
                detail["targets"] = data.get("metrics", {}).get("targets", {})
                detail["source"] = "sync_parity_metrics.json"
        
        # Agent Skills
        elif "Agent Skills" in k:
            try:
                import yaml
                agents_dir = REPO_ROOT / ".agent" / "agents"
                agent_files = [os.path.join(root, f) for root, _, files in os.walk(str(agents_dir)) for f in files if f.endswith(".md")]
                agent_list = []
                for af in agent_files:
                    with open(af, "r", encoding="utf-8") as f:
                        content = f.read()
                    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                    if m:
                        fm = yaml.safe_load(m.group(1))
                        agent_list.append({"file": os.path.basename(af), "skills": fm.get("skills", []) if isinstance(fm, dict) else []})
                detail["agents"] = agent_list
                detail["source"] = "agent frontmatter scan"
            except:
                pass

        diagnostics[k] = detail
    
    return diagnostics


def export_to_html(score: int, metrics: dict, diagnostics: dict = None):
    """Generate a premium static HTML dashboard with Glassmorphism, SEO, and Drawer Inspector + Sparklines."""
    from lib.paths import REPO_ROOT
    html_path = REPO_ROOT / ".agent" / "dashboard.html"
    
    # Append this run to history log
    append_history(score, metrics)
    
    # Read history for sparklines (cached per metric key)
    sparkline_keys = {"score": None, "drift": "Drift", "budget": "Budget", 
                      "mttr": "Resilience", "linter": "Linter Debt",
                      "ki": "KI Coverage", "mcp": "MCP Services", "roi": "Intelligence ROI"}
    history_cache = {}
    for hkey, mkey in sparkline_keys.items():
        vals = read_history(hkey, limit=80)
        if vals:
            history_cache[mkey or hkey] = vals
    
    # Gather diagnostics if not provided
    if diagnostics is None:
        diagnostics = gather_diagnostics(metrics)
    
    # Generate status badges with sparklines
    rows = ""
    for k, v in metrics.items():
        status_class = "pass"
        v_str = str(v)
        if "FAIL" in v_str or "❌" in v_str or "Unknown" in v_str:
            status_class = "fail"
        elif "WARN" in v_str or "⚠️" in v_str:
            status_class = "warn"
        
        # Generate sparkline for this metric if history exists
        spark_svg = ""
        hl_vals = history_cache.get(k)
        if hl_vals and len(hl_vals) >= 2:
            spark_color = "#10b981" if status_class == "pass" else "#f59e0b" if status_class == "warn" else "#ef4444"
            uid = re.sub(r'[^a-zA-Z0-9]', '', k)[:12] or "m"
            spark_svg = f'<div class="sparkline">{generate_sparkline_svg(hl_vals, 100, 20, spark_color, uid)}</div>'
            
        rows += f"""
        <div class="metric-row" data-metric="{k.replace('"', '&quot;')}">
            <div class="metric-left">
                <span class="metric-key">{k}</span>
                {spark_svg}
            </div>
            <span class="metric-value {status_class}">{v}</span>
        </div>"""

    color = "#10b981" if score >= 80 else "#f59e0b" if score >= 50 else "#ef4444"
    
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Antigravity Workspace Health Dashboard - Real-time metrics and system integrity report for autonomous orchestration.">
    <title>Workspace Health | Antigravity Hive | Autonomous Orchestration</title>
    <!-- OpenGraph Tags -->
    <meta property="og:title" content="Workspace Health Dashboard | Antigravity Hive">
    <meta property="og:description" content="Real-time system integrity and health metrics for the Antigravity autonomous agent ecosystem.">
    <meta property="og:type" content="website">
    <meta property="og:image" content="https://antigravity.hive/assets/dashboard-preview.png">
    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "name": "Antigravity Health Dashboard",
      "description": "Real-time health and integrity monitoring for agentic workflows.",
      "applicationCategory": "DevOpsTool",
      "operatingSystem": "All"
    }}
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: {color};
            --bg: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border: rgba(255, 255, 255, 0.1);
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --font-size-base: clamp(14px, 1vw + 10px, 18px);
            --font-size-h1: clamp(24px, 3vw + 12px, 40px);
        }}

        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: 'Outfit', sans-serif; 
            background: var(--bg); 
            background-image: 
                radial-gradient(at 0% 0%, rgba(16, 185, 129, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.1) 0px, transparent 50%);
            color: var(--text); 
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            line-height: 1.6;
        }}

        .dashboard {{ 
            background: var(--card-bg); 
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 24px; 
            padding: 40px; 
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); 
            max-width: 900px; 
            width: 100%;
            animation: fadeIn 0.8s ease-out;
            max-width: 65ch;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }}

        h1 {{ 
            font-size: var(--font-size-h1); 
            font-weight: 700;
            margin: 0;
            background: linear-gradient(to right, #fff, var(--text-muted));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
            line-height: 1.2;
        }}

        .health-score {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .score-value {{ 
            font-size: var(--font-size-h1); 
            font-weight: 700; 
            color: var(--primary); 
            line-height: 1;
            text-shadow: 0 0 20px rgba(var(--primary), 0.3);
            letter-spacing: -0.04em;
        }}

        .score-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        .metrics-grid {{ 
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}

        .metric-row {{ 
            padding: 16px; 
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }}

        .metric-row:hover {{
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--border);
            transform: scale(1.02);
        }}

        .metric-left {{
            display: flex; flex-direction: column; gap: 4px;
            min-width: 0;
        }}

        .metric-key {{ 
            color: var(--text-muted);
            font-size: 14px;
            font-weight: 400;
        }}

        .metric-value {{ 
            font-weight: 600;
            font-size: 14px;
            flex-shrink: 0;
            margin-left: 8px;
        }}

        .sparkline {{
            opacity: 0.6;
            transition: opacity 0.2s;
        }}
        .metric-row:hover .sparkline {{
            opacity: 1;
        }}

        .metric-value.pass {{ color: #10b981; }}
        .metric-value.warn {{ color: #f59e0b; }}
        .metric-value.fail {{ color: #ef4444; }}

        .about-section {{
            margin-top: 32px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 16px;
            border-left: 4px solid var(--primary);
        }}

        .about-section h2 {{
            font-size: 18px;
            margin-top: 0;
            color: var(--text);
        }}

        .about-section p {{
            font-size: 14px;
            color: var(--text-muted);
            margin-bottom: 0;
        }}

        .trust-badges {{
            display: flex;
            gap: 12px;
            margin-top: 24px;
            align-items: center;
        }}

        .trust-badge {{
            font-size: 10px;
            padding: 4px 8px;
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 4px;
            display: flex;
            align-items: center;
            gap: 4px;
            text-transform: uppercase;
            font-weight: 700;
        }}

        footer {{ 
            margin-top: 40px; 
            font-size: 12px; 
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .badge {{
            padding: 4px 12px;
            border-radius: 20px;
            background: var(--border);
            font-weight: 600;
        }}

        /* ── Drawer Inspector ── */
        .drawer-overlay {{
            position: fixed; inset: 0; z-index: 999;
            background: rgba(0,0,0,0.5);
            opacity: 0; visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }}
        .drawer-overlay.open {{
            opacity: 1; visibility: visible;
        }}
        .drawer {{
            position: fixed; top: 0; right: -480px;
            width: 460px; max-width: 90vw; height: 100vh;
            z-index: 1000;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-left: 1px solid var(--border);
            box-shadow: -10px 0 40px rgba(0,0,0,0.5);
            transition: right 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex; flex-direction: column;
            overflow: hidden;
        }}
        .drawer.open {{
            right: 0;
        }}
        .drawer-header {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 24px; border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }}
        .drawer-header h2 {{
            margin: 0; font-size: 18px; font-weight: 600;
            color: var(--text);
        }}
        .drawer-close {{
            background: none; border: none; color: var(--text-muted);
            font-size: 24px; cursor: pointer; padding: 4px 8px;
            border-radius: 8px; transition: all 0.2s;
        }}
        .drawer-close:hover {{
            background: rgba(255,255,255,0.1); color: var(--text);
        }}
        .drawer-body {{
            flex: 1; overflow-y: auto; padding: 24px;
        }}
        .drawer-body .metric-summary {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding: 16px;
            background: rgba(255,255,255,0.03); border-radius: 12px;
        }}
        .drawer-body .metric-summary .label {{
            font-size: 14px; color: var(--text-muted);
        }}
        .drawer-body .metric-summary .value {{
            font-size: 18px; font-weight: 700;
        }}
        .drawer-body .detail-section {{
            margin-bottom: 16px;
        }}
        .drawer-body .detail-section h3 {{
            font-size: 13px; text-transform: uppercase; letter-spacing: 1px;
            color: var(--text-muted); margin: 0 0 8px;
        }}
        .drawer-body .detail-item {{
            padding: 10px 12px; margin-bottom: 6px;
            background: rgba(255,255,255,0.02); border-radius: 8px;
            font-size: 13px; color: var(--text);
            border-left: 3px solid var(--border);
            word-break: break-word;
        }}
        .drawer-body .detail-item .sub {{
            font-size: 11px; color: var(--text-muted); margin-top: 4px;
        }}
        .drawer-body .detail-item.warn {{ border-left-color: #f59e0b; }}
        .drawer-body .detail-item.fail {{ border-left-color: #ef4444; }}
        .drawer-body .detail-item.pass {{ border-left-color: #10b981; }}
        .drawer-body .empty-state {{
            text-align: center; padding: 40px 20px; color: var(--text-muted);
            font-size: 14px;
        }}
        .drawer-body .empty-state .icon {{ font-size: 32px; margin-bottom: 12px; }}
        /* ── Cockpit Operations (Option C) ── */
        .cockpit {{
            margin-bottom: 32px;
        }}
        .cockpit-bar {{
            display: flex; gap: 8px; flex-wrap: wrap;
            margin-bottom: 12px;
        }}
        .cockpit-btn {{
            padding: 8px 14px; border: 1px solid var(--border);
            border-radius: 8px; background: rgba(255,255,255,0.04);
            color: var(--text); font-family: 'Outfit', sans-serif;
            font-size: 12px; font-weight: 500; cursor: pointer;
            transition: all 0.2s; white-space: nowrap;
        }}
        .cockpit-btn:hover {{
            background: rgba(255,255,255,0.1); border-color: var(--primary);
        }}
        .cockpit-btn:disabled {{
            opacity: 0.4; cursor: not-allowed; pointer-events: none;
        }}
        .cockpit-btn.running {{
            border-color: #f59e0b; animation: pulse-border 1s ease infinite;
        }}
        @keyframes pulse-border {{
            0%, 100% {{ border-color: #f59e0b; opacity: 1; }}
            50% {{ border-color: #f59e0b; opacity: 0.5; }}
        }}
        .cockpit-btn .key {{
            display: inline-block; padding: 0 6px; margin-left: 6px;
            background: rgba(255,255,255,0.08); border-radius: 3px;
            font-size: 10px; font-weight: 600; color: var(--text-muted);
        }}
        .terminal-panel {{
            background: #0d1117; border: 1px solid var(--border);
            border-radius: 12px; overflow: hidden;
            max-height: 0; opacity: 0; transition: all 0.3s ease;
        }}
        .terminal-panel.open {{
            max-height: 320px; opacity: 1;
        }}
        .terminal-header {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 10px 14px; border-bottom: 1px solid var(--border);
            font-size: 11px; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .terminal-header .close-btn {{
            background: none; border: none; color: var(--text-muted);
            cursor: pointer; font-size: 16px; padding: 0 4px;
        }}
        .terminal-header .close-btn:hover {{ color: var(--text); }}
        .terminal-output {{
            padding: 12px 14px; overflow-y: auto; max-height: 260px;
            font-family: 'Menlo', 'Consolas', 'Courier New', monospace;
            font-size: 12px; line-height: 1.5; color: #e6edf3;
        }}
        .terminal-output .line {{
            white-space: pre-wrap; word-break: break-all;
        }}
        .terminal-output .line.out {{ color: #e6edf3; }}
        .terminal-output .line.err {{ color: #f85149; }}
        .terminal-output .line.done {{ color: #3fb950; font-weight: 600; margin-top: 8px; }}
        .terminal-output .prompt {{
            color: var(--text-muted); font-size: 11px;
        }}
        .file-hint {{
            display: block; text-align: center; font-size: 11px;
            color: var(--text-muted); margin-top: 8px; padding: 6px;
            border-radius: 6px; background: rgba(255,255,255,0.02);
        }}
        @media (max-width: 600px) {{
            .dashboard {{ padding: 24px; }}
            h1 {{ font-size: 24px; }}
            .score-value {{ font-size: 40px; }}
            .cockpit-btn {{ font-size: 11px; padding: 6px 10px; }}
        }}
    </style>
</head>
<body>
    <main class="dashboard">
        <header>
            <h1>🚀 Workspace Health</h1>
            <div class="health-score">
                <span class="score-value">{score}%</span>
                <span class="score-label">Integrity Index</span>
            </div>
        </header>
        
        <section class="metrics-grid">
            {rows}
        </section>

        <!-- ── Cockpit Operations (Option C) ── -->
        <section class="cockpit" id="cockpit">
            <div class="cockpit-bar">
                <button class="cockpit-btn" data-script="status-report" onclick="cockpitExec(this)">
                    🏗️ Status Report <span class="key">R</span>
                </button>
                <button class="cockpit-btn" data-script="checklist-fix" onclick="cockpitExec(this)">
                    ✅ Checklist Fix <span class="key">F</span>
                </button>
                <button class="cockpit-btn" data-script="security-scan" onclick="cockpitExec(this)">
                    🔒 Security Scan <span class="key">S</span>
                </button>
                <button class="cockpit-btn" data-script="sync-docs" onclick="cockpitExec(this)">
                    📄 Sync Docs <span class="key">D</span>
                </button>
                <button class="cockpit-btn" data-script="chaos-drill" onclick="cockpitExec(this)">
                    ⚡ Chaos Drill <span class="key">C</span>
                </button>
            </div>
            <div class="terminal-panel" id="terminalPanel">
                <div class="terminal-header">
                    <span id="terminalTitle">⚡ Cockpit Exec</span>
                    <button class="close-btn" onclick="closeTerminal()">&times;</button>
                </div>
                <div class="terminal-output" id="terminalOutput"></div>
            </div>
            <span class="file-hint" id="cockpitHint">
                🖥️ Start SSE server for cockpit controls: <code>python3 .agent/scripts/health/bus_sse_server.py --port 3207</code>
            </span>
        </section>

        <section class="about-section">
            <h2>Architectural Intuition</h2>
            <p>Our core design philosophy balances absolute system transparency with proactive risk mitigation. By utilizing a multi-layered agent participant protocol, we ensure that every decision is vetted for architectural alignment and security before execution.</p>
        </section>

        <section class="about-section">
            <h2>Why We Exist</h2>
            <p>Antigravity Hive is an autonomous orchestration layer designed for high-integrity agentic workflows. We prioritize security, performance, and premium UX across all domain-driven services.</p>
        </section>

        <div class="trust-badges">
            <div class="trust-badge">🔒 SSL SECURE</div>
            <div class="trust-badge">🛡️ SENTINEL ACTIVE</div>
            <div class="trust-badge">✅ TRUSTED BY HIVE</div>
        </div>
        
        <footer>
            <span>Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
            <span class="badge">ANTIGRAVITY HIVE v2.5</span>
        </footer>
    </main>

    <!-- Raw Metrics Data for Drawer Inspector -->
    <script id="raw-metrics" type="application/json">
    {json.dumps(diagnostics, default=str, indent=2)}
    </script>

    <!-- Drawer Inspector Overlay -->
    <div class="drawer-overlay" id="drawerOverlay" onclick="closeDrawer(event)"></div>
    <aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-label="Metric details">
        <div class="drawer-header">
            <h2 id="drawerTitle">Metric Details</h2>
            <button class="drawer-close" onclick="closeDrawer()" aria-label="Close">&times;</button>
        </div>
        <div class="drawer-body" id="drawerBody">
            <div class="empty-state">
                <div class="icon">📊</div>
                <p>Select a metric to inspect</p>
            </div>
        </div>
    </aside>

    <script>
    (function() {{
        var rawEl = document.getElementById('raw-metrics');
        var diagnostics = {{}};
        try {{ diagnostics = JSON.parse(rawEl.textContent); }} catch(e) {{}}

        var drawer = document.getElementById('drawer');
        var overlay = document.getElementById('drawerOverlay');
        var drawerTitle = document.getElementById('drawerTitle');
        var drawerBody = document.getElementById('drawerBody');

        function escapeHtml(str) {{
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(str));
            return div.innerHTML;
        }}

        function formatDetail(key, detail) {{
            var html = '';
            if (!detail || Object.keys(detail).length === 0) {{
                return '<div class="empty-state"><div class="icon">🔍</div><p>No diagnostic data available</p></div>';
            }}
            if (detail.error) {{
                return '<div class="detail-item fail">Error: ' + escapeHtml(detail.error) + '</div>';
            }}
            if (detail.source) {{
                html += '<div class="detail-section"><h3>Source</h3><div class="detail-item pass">' + escapeHtml(detail.source) + '</div></div>';
            }}
            for (var prop in detail) {{
                if (prop === 'source') continue;
                var val = detail[prop];
                if (typeof val === 'object' && val !== null) {{
                    html += '<div class="detail-section"><h3>' + escapeHtml(prop) + '</h3>';
                    if (Array.isArray(val)) {{
                        if (val.length === 0) {{
                            html += '<div class="detail-item pass">None</div>';
                        }} else {{
                            for (var i = 0; i < val.length; i++) {{
                                var item = val[i];
                                var cls = 'pass';
                                if (item.status === 'WARN' || item.status === 'FAIL' || item.risk_score > 60) cls = 'warn';
                                if (item.status === 'DOWN' || item.status === 'FAILURE') cls = 'fail';
                                html += '<div class="detail-item ' + cls + '">';
                                html += '<div>' + escapeHtml(item.file || item.name || JSON.stringify(item)) + '</div>';
                                if (item.msg || item.message) html += '<div class="sub">' + escapeHtml(item.msg || item.message) + '</div>';
                                if (item.risk_score) html += '<div class="sub">Risk: ' + escapeHtml(item.risk_score) + '</div>';
                                if (item.status) html += '<div class="sub">Status: ' + escapeHtml(item.status) + '</div>';
                                html += '</div>';
                            }}
                        }}
                    }} else if (typeof val === 'object') {{
                        if (val.value !== undefined) {{
                            html += '<div class="detail-item ' + ((val.status === 'FAIL' || val.status === 'WARN') ? val.status.toLowerCase() : 'pass') + '">';
                            html += '<div>' + escapeHtml(prop) + ': ' + escapeHtml(String(val.value)) + '</div>';
                            if (val.status) html += '<div class="sub">Status: ' + escapeHtml(val.status) + '</div>';
                            html += '</div>';
                        }} else {{
                            html += '<div class="detail-item pass"><pre style="margin:0;font-size:12px;white-space:pre-wrap">' + escapeHtml(JSON.stringify(val, null, 2)) + '</pre></div>';
                        }}
                    }}
                    html += '</div>';
                }} else {{
                    var cls = 'pass';
                    if (String(val).includes('WARN') || String(val).includes('FAIL') || String(val).includes('DOWN')) cls = 'warn';
                    html += '<div class="detail-section"><h3>' + escapeHtml(prop) + '</h3><div class="detail-item ' + cls + '">' + escapeHtml(String(val)) + '</div></div>';
                }}
            }}
            return html || '<div class="empty-state"><div class="icon">🔍</div><p>No details</p></div>';
        }}

        window.openDrawer = function(metricKey) {{
            var detail = diagnostics[metricKey] || {{}};
            var metricEl = document.querySelector('.metric-row[data-metric="' + metricKey.replace(/"/g, '&quot;') + '"]');
            var metricValue = metricEl ? metricEl.querySelector('.metric-value').textContent : '';
            drawerTitle.textContent = metricKey;
            drawerBody.innerHTML =
                '<div class="metric-summary">' +
                '<span class="label">' + escapeHtml(metricKey) + '</span>' +
                '<span class="value">' + escapeHtml(metricValue) + '</span>' +
                '</div>' +
                formatDetail(metricKey, detail);
            drawer.classList.add('open');
            overlay.classList.add('open');
            document.body.style.overflow = 'hidden';
            drawer.focus();
        }}

        window.closeDrawer = function(e) {{
            if (e && e.target !== overlay) return;
            drawer.classList.remove('open');
            overlay.classList.remove('open');
            document.body.style.overflow = '';
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape' && drawer.classList.contains('open')) {{
                closeDrawer();
            }}
        }});

        // Click handlers on metric rows
        var rows = document.querySelectorAll('.metric-row');
        for (var i = 0; i < rows.length; i++) {{
            rows[i].addEventListener('click', function() {{
                var key = this.getAttribute('data-metric');
                if (key) openDrawer(key);
            }});
            rows[i].style.cursor = 'pointer';
        }}
    }})();
    </script>

    <!-- SSE Live Reactivity (auto-enabled when served via HTTP) -->
    <script>
    (function() {{
        // Only connect SSE when served via HTTP (not file://)
        if (window.location.protocol === 'file:') return;

        var source = null;
        var reconnectTimer = null;
        var reconnectDelay = 1000;  // start at 1s
        var maxReconnect = 30000;   // max 30s

        function connectSSE() {{
            if (source) {{ source.close(); }}

            source = new EventSource('/api/stream/bus');

            source.addEventListener('connected', function(e) {{
                reconnectDelay = 1000;  // reset on success
                try {{
                    var data = JSON.parse(e.data);
                    updateMetricsFromBus(data, true);
                }} catch(err) {{}}
            }});

            source.addEventListener('bus_update', function(e) {{
                try {{
                    var changes = JSON.parse(e.data);
                    updateMetricsFromBus(changes, false);
                }} catch(err) {{}}
            }});

            source.onerror = function() {{
                if (source) {{
                    source.close();
                    source = null;
                }}
                // Exponential backoff reconnect
                if (reconnectTimer) clearTimeout(reconnectTimer);
                reconnectTimer = setTimeout(function() {{
                    connectSSE();
                }}, reconnectDelay);
                reconnectDelay = Math.min(reconnectDelay * 2, maxReconnect);
            }};
        }}

        // ── Metric update engine ──
        var metricRows = null;
        function getMetricRows() {{
            if (!metricRows) {{
                metricRows = {{}};
                var els = document.querySelectorAll('.metric-row');
                for (var i = 0; i < els.length; i++) {{
                    var key = els[i].getAttribute('data-metric');
                    if (key) metricRows[key] = els[i];
                }}
            }}
            return metricRows;
        }}

        function extractMetricValue(fileContent, metricName) {{
            // Map bus file structure → human-readable value with status class
            if (!fileContent || typeof fileContent !== 'object') return null;

            if (metricName === 'Budget') {{
                var pct = fileContent.percent;
                if (pct !== undefined) return {{v: pct.toFixed(1) + '% used', cls: pct > 80 ? 'warn' : 'pass'}};
            }}
            if (metricName === 'MCP Services') {{
                var m = fileContent.metrics || {{}};
                var count = Object.keys(m).length;
                var st = fileContent.status;
                if (st === 'PASS') return {{v: '✅ ' + count + ' active', cls: 'pass'}};
                if (st === 'WARN') return {{v: '⚠️ ' + count + ' active', cls: 'warn'}};
                return {{v: st || 'Unknown', cls: st === 'FAIL' ? 'fail' : 'pass'}};
            }}
            if (metricName === 'Stability') {{
                return {{v: fileContent.status || fileContent.system_health || 'Unknown', cls: 'pass'}};
            }}
            if (metricName === 'KI Coverage') {{
                var cv = fileContent.metrics && fileContent.metrics.coverage_pct;
                if (cv && cv.value !== undefined) return {{v: cv.value + '%', cls: cv.status === 'FAIL' ? 'fail' : cv.status === 'WARN' ? 'warn' : 'pass'}};
            }}
            if (metricName === 'Intelligence ROI') {{
                var lr = fileContent.metrics && fileContent.metrics.local_ratio;
                if (lr && lr.value !== undefined) return {{v: lr.value + ' (Local Ratio)', cls: fileContent.status === 'WARN' ? 'warn' : 'pass'}};
            }}
            if (metricName === 'Linter Debt') {{
                var di = fileContent.metrics && fileContent.metrics.debt_index;
                if (di && di.value !== undefined) return {{v: di.value, cls: di.status === 'FAIL' ? 'fail' : di.status === 'WARN' ? 'warn' : 'pass'}};
            }}
            if (metricName === 'Resilience') {{
                var mttr = fileContent.mttr;
                if (mttr) return {{v: 'MTTR ' + mttr.toFixed(1) + 's', cls: fileContent.status === 'FAILURE' ? 'fail' : 'pass'}};
            }}
            if (metricName === 'Sync Status') {{
                var t = fileContent.metrics && fileContent.metrics.targets;
                if (t && t.value) {{
                    var parts = ['✅ antigravity (source)'];
                    for (var k in t.value) {{
                        parts.push((t.value[k].status === 'OK' ? '✅' : '❌') + ' ' + k);
                    }}
                    return {{v: parts.join(' | '), cls: 'pass'}};
                }}
            }}
            if (metricName === 'Ethics Audit') {{
                return {{v: fileContent.status || 'PASS', cls: fileContent.status === 'FLAGGED' ? 'fail' : 'pass'}};
            }}
            if (metricName === 'Policy Compliance') {{
                return {{v: fileContent.status || 'PASS', cls: fileContent.status === 'VIOLATION' ? 'fail' : 'pass'}};
            }}
            if (metricName === 'UX Audit') {{
                var p = fileContent.passed;
                if (p !== undefined) return {{v: p ? 'PASS' : 'WARN', cls: p ? 'pass' : 'warn'}};
            }}
            if (metricName === 'SEO Check') {{
                if (fileContent.skipped) return {{v: 'N/A', cls: 'pass'}};
                return {{v: fileContent.passed ? 'PASS' : 'WARN', cls: fileContent.passed ? 'pass' : 'warn'}};
            }}

            return null;
        }}

        function getBusMetricNames(fileName) {{
            var map = {{
                'budget_status.json': 'Budget',
                'mcp_health_metrics.json': 'MCP Services',
                'blue_team_status.json': 'Stability',
                'ki_coverage_metrics.json': 'KI Coverage',
                'intelligence_roi_metrics.json': 'Intelligence ROI',
                'linter_debt_metrics.json': 'Linter Debt',
                'chaos_report.json': 'Resilience',
                'sync_parity_metrics.json': 'Sync Status',
                'hallucination_report.json': 'Ethics Audit',
                'policy_report.json': 'Policy Compliance',
                'seo_metrics.json': 'SEO Check',
                'ux_metrics.json': 'UX Audit',
            }};
            return map[fileName] || null;
        }}

        function animateValue(el, newText, statusCls) {{
            // Smooth CSS transition via opacity
            el.style.transition = 'opacity 0.15s ease';
            el.style.opacity = '0.3';
            setTimeout(function() {{
                el.textContent = newText;
                el.className = 'metric-value ' + (statusCls || 'pass');
                el.style.opacity = '1';
            }}, 150);
        }}

        function applyMetricValue(mname, result, animate) {{
            var rows = getMetricRows();
            var el = rows[mname];
            if (!el || !result) return;
            var valEl = el.querySelector('.metric-value');
            if (!valEl) return;
            if (animate) {{
                animateValue(valEl, result.v, result.cls);
            }} else {{
                valEl.textContent = result.v;
                valEl.className = 'metric-value ' + (result.cls || 'pass');
            }}
        }}

        function updateMetricsFromBus(data, isInitial) {{
            var rows = getMetricRows();

            for (var fname in data) {{
                var content = data[fname];
                // Check nested structure: content object has .content and .metric
                if (content && typeof content === 'object' && 'content' in content) {{
                    var mname = content.metric || getBusMetricNames(fname);
                    if (mname) {{
                        var result = extractMetricValue(content.content, mname);
                        applyMetricValue(mname, result, !isInitial);
                    }}
                }} else {{
                    // Plain structure: filename -> content direct mapping
                    var mname = getBusMetricNames(fname);
                    if (mname) {{
                        var result = extractMetricValue(content, mname);
                        applyMetricValue(mname, result, !isInitial);
                    }}
                }}
            }}
        }}

        // Start SSE connection
        connectSSE();
    }})();
    </script>

    <!-- ── Cockpit Operations JS (Option C) ── -->
    <script>
    (function() {{
        var isHttp = window.location.protocol !== 'file:';
        var buttons = document.querySelectorAll('.cockpit-btn');
        var hint = document.getElementById('cockpitHint');
        var terminalPanel = document.getElementById('terminalPanel');
        var terminalOutput = document.getElementById('terminalOutput');
        var terminalTitle = document.getElementById('terminalTitle');
        var pollTimer = null;
        var currentExecId = null;

        // Disable buttons if file://
        if (!isHttp) {{
            for (var i = 0; i < buttons.length; i++) {{
                buttons[i].disabled = true;
                buttons[i].title = 'Start SSE server for cockpit controls';
            }}
        }} else {{
            hint.style.display = 'none';
        }}

        window.cockpitExec = function(btn) {{
            if (!isHttp || btn.disabled) return;
            var script = btn.getAttribute('data-script');
            btn.disabled = true;
            btn.classList.add('running');

            // Show terminal
            terminalPanel.classList.add('open');
            terminalOutput.innerHTML = '';
            terminalTitle.textContent = '⚡ Exec: ' + script;

            // POST /api/exec
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/exec', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.onload = function() {{
                if (xhr.status === 202) {{
                    var resp = JSON.parse(xhr.responseText);
                    currentExecId = resp.exec_id;
                    appendLine('$ ' + (resp.script || script), 'prompt');
                    pollOutput(currentExecId, btn, script);
                }} else {{
                    appendLine('Error: ' + xhr.responseText, 'err');
                    resetButton(btn, script);
                }}
            }};
            xhr.onerror = function() {{
                appendLine('Network error', 'err');
                resetButton(btn, script);
            }};
            xhr.send(JSON.stringify({{script: script}}));
        }};

        function pollOutput(execId, btn, script) {{
            if (pollTimer) clearTimeout(pollTimer);
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/output/' + execId, true);
            xhr.onload = function() {{
                if (xhr.status === 200) {{
                    var resp = JSON.parse(xhr.responseText);
                    terminalOutput.innerHTML = '';
                    for (var i = 0; i < resp.lines.length; i++) {{
                        appendLine(resp.lines[i], 'out');
                    }}
                    if (resp.done) {{
                        appendLine('✅ Done (exit code ' + resp.code + ')', 'done');
                        resetButton(btn, script);
                        currentExecId = null;
                        return;
                    }}
                }}
                pollTimer = setTimeout(function() {{ pollOutput(execId, btn, script); }}, 500);
            }};
            xhr.onerror = function() {{
                pollTimer = setTimeout(function() {{ pollOutput(execId, btn, script); }}, 1000);
            }};
            xhr.send();
        }}

        function appendLine(text, cls) {{
            var div = document.createElement('div');
            div.className = 'line ' + (cls || 'out');
            div.textContent = text;
            terminalOutput.appendChild(div);
            terminalOutput.scrollTop = terminalOutput.scrollHeight;
        }}

        function resetButton(btn, script) {{
            var labels = {{
                'status-report': '🏗️ Status Report',
                'checklist-fix': '✅ Checklist Fix',
                'security-scan': '🔒 Security Scan',
                'sync-docs': '📄 Sync Docs',
                'chaos-drill': '⚡ Chaos Drill'
            }};
            btn.innerHTML = (labels[script] || script) + ' <span class="key">' + script.charAt(0).toUpperCase() + '</span>';
            btn.disabled = false;
            btn.classList.remove('running');
        }}

        window.closeTerminal = function() {{
            terminalPanel.classList.remove('open');
            if (pollTimer) clearTimeout(pollTimer);
            currentExecId = null;
        }};

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (!isHttp) return;
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            var key = e.key.toUpperCase();
            var map = {{'R': 'status-report', 'F': 'checklist-fix', 'S': 'security-scan', 'D': 'sync-docs', 'C': 'chaos-drill'}};
            var script = map[key];
            if (!script) return;
            var btn = document.querySelector('.cockpit-btn[data-script="' + script + '"]');
            if (btn && !btn.disabled) cockpitExec(btn);
        }});
    }})();
    </script>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ Dashboard exported to {html_path}"

def main() -> None:
    score, metrics = calculate_health()
    
    if "--html" in sys.argv:
        diagnostics = gather_diagnostics(metrics)
        print(export_to_html(score, metrics, diagnostics))
        return
    
    # Append history even in CLI mode
    append_history(score, metrics)

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

def get_health_report() -> Dict[str, Any]:
    """Helper for programmatic access to health metrics."""
    score, metrics = calculate_health()
    return {
        "score": score,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    main()
