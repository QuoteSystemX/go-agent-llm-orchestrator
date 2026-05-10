#!/usr/bin/env python3
"""Unified Model Router 2.2 — Hybrid Local/Cloud Routing.

Supports Ollama (local) as primary provider with automatic cloud fallback
when Ollama is unreachable or when the tier requires cloud-only execution.
"""
import json
import sys
import os
import re
import argparse
import urllib.request
import urllib.error
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

def resolve_env_var(value: str) -> str:
    """Resolve environment variables in string like ${VAR:-default}."""
    if not isinstance(value, str):
        return value
    
    # Match ${VAR} or ${VAR:-default}
    match = re.match(r"\$\{(?P<var>[^:-]+)(?::-(?P<default>.*))?\}", value)
    if not match:
        return value
    
    var_name = match.group("var")
    default_val = match.group("default") or ""
    
    return os.environ.get(var_name, default_val)

@dataclass
class RoutingResult:
    """Routing decision returned by route()."""
    model_id: str
    tier: str
    provider: str
    score: int
    # Non-empty when Ollama was alive but models weren't pulled — action required.
    warning: str = ""
    # Shell commands user can run to fix the warning.
    pull_hints: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Compact representation for CLI / logging."""
        return self.model_id


# Setup paths
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

try:
    from lib.paths import ROUTER_RULES_PATH as RULES_FILE, TELEMETRY_PATH, LESSONS_PATH
    from lib.common import load_json_safe
    import bus_manager
except ImportError:
    # When lib.common is unavailable, provide minimal fallback
    RULES_FILE = REPO_ROOT / ".agent" / "config" / "router_rules.json"
    TELEMETRY_PATH = REPO_ROOT / ".agent" / "bus" / "telemetry.json"
    LESSONS_PATH = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"
    bus_manager = None
    def load_json_safe(path):
        if not Path(path).exists(): return {}
        try:
            with open(path, 'r') as f: return json.load(f)
        except: return {}

def log_routing_event(task, score, tier, model_id):
    """Log the routing decision to telemetry.json for transparency."""
    try:
        telemetry = load_json_safe(TELEMETRY_PATH)
        if "events" not in telemetry: telemetry["events"] = []
        
        from datetime import datetime
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "routing",
            "task": task[:100] + "..." if len(task) > 100 else task,
            "score": score,
            "tier": tier,
            "model_id": model_id
        }
        
        telemetry["events"].append(event)
        # Keep only last 50 events
        if len(telemetry["events"]) > 50:
            telemetry["events"] = telemetry["events"][-50:]
            
        with open(TELEMETRY_PATH, 'w') as f:
            json.dump(telemetry, f, indent=2)
            
        # Push to Context Bus for cross-agent visibility (ADR-006)
        if bus_manager:
            try:
                event_id = f"route-{int(datetime.now().timestamp())}"
                bus_manager.push(
                    obj_id=event_id,
                    obj_type="routing_event",
                    author="model-router",
                    content_str=json.dumps(event)
                )
            except Exception as e:
                # Don't fail the whole routing if bus is busy
                print(f"⚠️ Bus push failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Telemetry log failed: {e}", file=sys.stderr)

def _is_wsl() -> bool:
    """Detect if running inside WSL."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except Exception:
        return False

def _get_wsl_gateway() -> str:
    """Get the IP of the Windows host from WSL."""
    try:
        # Use ip route to find the default gateway
        output = subprocess.check_output("ip route show default", shell=True, text=True)
        return output.split()[2]
    except Exception:
        return ""

def check_ollama_health(base_url: str, timeout_ms: int = 1500) -> bool:
    """Ping Ollama's /api/tags endpoint to verify it's running locally."""
    if not base_url: return False
    try:
        url = base_url.rstrip("/") + "/api/tags"
        timeout_sec = timeout_ms / 1000
        req = urllib.request.urlopen(url, timeout=timeout_sec)
        return req.status == 200
    except Exception:
        return False

def discover_ollama_url(configured_url: str, timeout_ms: int = 500) -> tuple[str, str]:
    """Smart Discovery Chain for Ollama.
    
    Returns (discovered_url, reason).
    """
    candidates = []
    if configured_url and configured_url != "auto":
        candidates.append((configured_url, "configured"))
    
    # Standard local options
    candidates.append(("http://localhost:11434", "localhost"))
    candidates.append(("http://127.0.0.1:11434", "loopback"))
    
    # WSL specific
    if _is_wsl():
        gw = _get_wsl_gateway()
        if gw:
            candidates.append((f"http://{gw}:11434", "WSL gateway"))
            
    # Docker specific
    candidates.append(("http://host.docker.internal:11434", "docker bridge"))

    for url, reason in candidates:
        if check_ollama_health(url, timeout_ms):
            return url, reason
            
    return None, "none found"


def resolve_provider(rules: dict) -> tuple[str, bool, str]:
    """Determine which provider to use.
    
    Returns (provider_name, is_ollama_available, discovered_url).
    """
    # Manual override via env var always wins
    if os.environ.get("AGENT_PROVIDER"):
        return os.environ.get("AGENT_PROVIDER").lower(), False, ""

    hybrid = rules.get("hybrid_routing", {})
    if not hybrid.get("enabled", False):
        return "antigravity", False, ""

    # Smart Discovery
    conf_url = hybrid.get("ollama_base_url", "http://localhost:11434")
    timeout = hybrid.get("ollama_health_timeout_ms", 1500)
    
    discovered_url, reason = discover_ollama_url(conf_url, timeout)
    ollama_alive = discovered_url is not None
    
    primary = hybrid.get("primary_provider", "ollama")
    return primary, ollama_alive, (discovered_url or conf_url)


def get_ollama_local_models(base_url: str) -> set[str]:
    """Fetch the list of models currently pulled in Ollama."""
    try:
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read())
            return {m["name"] for m in data.get("models", [])}
    except Exception:
        return set()


def pick_best_available(
    tier: str,
    model_map: dict,
    model_rankings: dict,
    ollama_alive: bool,
    ollama_base_url: str,
) -> tuple[str | None, str]:
    """Return (model_id, reason) choosing the best model by rank_score.

    rank_score = quality * 10 + tps * 0.1 - time * 0.5
    This considers quality, speed (TPS), and latency together.
    """
    primary = model_map.get(tier, "")
    alts: list[str] = model_map.get(f"{tier}_alt", [])

    # Sort by rank_score, highest first (considers quality + speed - latency)
    all_candidates = [primary] + [m for m in alts if m != primary]
    all_candidates.sort(
        key=lambda m: model_rankings.get(m, {}).get("rank_score", 0) 
        if "rank_score" in model_rankings.get(m, {}) 
        else model_rankings.get(m, {}).get("quality_score", 0) * 10,
        reverse=True
    )

    if ollama_alive:
        available = get_ollama_local_models(ollama_base_url)
        if available:
            for model in all_candidates:
                if model in available:
                    r = model_rankings.get(model, {})
                    rank = r.get("rank_score", 0)
                    reason = f"rank-score {rank:.1f}, locally available"
                    if model != primary:
                        reason += f" (over '{primary}')"
                    return model, reason
            # Ollama is up, but NONE of the candidates are pulled
            missing = ", ".join(f"`{m}`" for m in all_candidates[:3])
            return None, f"no local models pulled ({missing}) → cloud fallback"
        return None, "Ollama has no models pulled yet → cloud fallback"

    # Cloud provider — use quality ranking
    best = all_candidates[0] if all_candidates else primary
    reason = "quality-ranked"
    if best != primary:
        reason += f" (alt over '{primary}')"
    return best, reason


def detect_provider():
    """Legacy helper — returns provider string only (no health info)."""
    if os.environ.get("AGENT_PROVIDER"):
        return os.environ.get("AGENT_PROVIDER").lower()
    return "antigravity"

def get_failure_score(task_description):
    """Check for historical failures in KNOWLEDGE.md."""
    try:
        if not LESSONS_PATH.exists(): return 0
        content = LESSONS_PATH.read_text().lower()
        keywords = re.findall(r'\b\w{4,}\b', task_description.lower())
        
        failure_count = 0
        for kw in keywords:
            if kw in content:
                idx = content.find(kw)
                context = content[max(0, idx-100):min(len(content), idx+200)]
                if any(word in context for word in ["fail", "error", "retry", "broken", "bug", "hallucination"]):
                    failure_count += 1
        
        return min(failure_count, 3) 
    except Exception:
        return 0

def get_budget_penalty():
    """Check budget status from telemetry."""
    telemetry = load_json_safe(TELEMETRY_PATH)
    watchdog = load_json_safe(REPO_ROOT / ".agent" / "config" / "watchdog_rules.json")
    
    cost = telemetry.get("total_cost_usd", 0)
    limit = watchdog.get("limits", {}).get("cost_limit_per_task_usd", 2.0)
    
    if cost > (limit * 0.85): # 85% budget spent
        return -3 # Heavier penalty for L4 models
    return 0

def calculate_score(task_desc, rules):
    scoring = rules.get("scoring", {})
    weights = scoring.get("weights", {})
    
    score = 5 # Base score (L2)
    desc_lower = task_desc.lower()
    
    # 1. Keyword weights
    for kw, weight in weights.items():
        if kw in desc_lower:
            score += weight
            
    # 2. History bonus
    score += get_failure_score(task_desc)
    
    # 3. Budget penalty
    score += get_budget_penalty()
    
    return max(1, min(score, 18)) # Max score increased to 18 for L4

def route(task_description, override_model=None):
    rules = load_json_safe(RULES_FILE)

    if override_model:
        return RoutingResult(
            model_id=override_model,
            tier="L2", # Default tier for manual override
            provider="antigravity",
            score=5
        )

    # 1. Calculate Complexity Score
    score = calculate_score(task_description, rules)
    thresholds = rules.get("scoring", {}).get("thresholds", {"L1": 3, "L2": 7, "L3": 10, "L4": 13})

    if score <= thresholds["L1"]:
        tier = "L1"
    elif score <= thresholds["L2"]:
        tier = "L2"
    elif score <= thresholds["L3"]:
        tier = "L3"
    else:
        tier = "L4"

    # 2. Hybrid Provider Resolution
    hybrid = rules.get("hybrid_routing", {})
    primary_provider, ollama_alive, active_url = resolve_provider(rules)
    cloud_provider = hybrid.get("cloud_fallback_provider", "antigravity")
    cloud_only_tiers = hybrid.get("cloud_on_tiers", ["L4"])

    # Decide which provider to actually use
    if tier in cloud_only_tiers:
        target_provider = cloud_provider
        routing_reason = f"tier {tier} is cloud-only"
    elif primary_provider == "ollama" and ollama_alive:
        target_provider = "ollama"
        routing_reason = f"Ollama found at {active_url}"
    elif primary_provider == "ollama" and not ollama_alive:
        target_provider = cloud_provider
        routing_reason = "Ollama not found in search chain ⚠️ → cloud fallback"
    else:
        target_provider = primary_provider
        routing_reason = "explicit provider"

    # 3. Domain Affinity (can override provider for specific keywords)
    affinity = rules.get("domain_affinity", {})
    for domain, pref in affinity.items():
        if domain in task_description.lower():
            # Affinity only overrides if Ollama is NOT the primary or is unavailable
            if primary_provider != "ollama" or not ollama_alive:
                target_provider = pref
                routing_reason = f"domain affinity [{domain}]"
            break

    # 4. Quality-ranked Model Selection
    models = rules.get("models", {})
    model_rankings = rules.get("model_rankings", rules.get("model_quality_scores", {}))
    model_map = models.get(target_provider, models.get(cloud_provider, {}))
    ollama_url = hybrid.get("ollama_base_url", "http://localhost:11434")

    model_id, model_reason = pick_best_available(
        tier=tier,
        model_map=model_map,
        model_rankings=model_rankings,
        ollama_alive=(target_provider == "ollama" and ollama_alive),
        ollama_base_url=active_url,
    )

    # Build result early so we can attach warnings
    warning = ""
    pull_hints: list[str] = []

    # If no local model is available, transparently fall back to cloud
    if model_id is None:
        # Collect the candidates that need to be pulled
        raw_map = models.get("ollama", {})
        primary_model = raw_map.get(tier, "")
        alts: list[str] = raw_map.get(f"{tier}_alt", [])
        missing_models = [primary_model] + alts
        pull_hints = [f"ollama pull {m}" for m in missing_models if m]

        warning = (
            f"⚠️  Ollama is running but no models are pulled for tier {tier}.\n"
            f"   Request was sent to CLOUD ({cloud_provider}) as fallback.\n"
            f"   To use local models, run:\n"
            + "\n".join(f"     {cmd}" for cmd in pull_hints)
        )

        target_provider = cloud_provider
        routing_reason = f"Ollama: {model_reason}"
        cloud_map = models.get(cloud_provider, {})
        cloud_best, cloud_reason = pick_best_available(
            tier=tier,
            model_map=cloud_map,
            model_rankings=model_rankings,
            ollama_alive=False,
            ollama_base_url=ollama_url,
        )
        model_id = cloud_best or "gemini-3-flash"
        model_reason = cloud_reason

    # Log Routing Decision — always to stderr to keep stdout clean
    provider_icon = "🏠" if target_provider == "ollama" else "☁️"
    print(f"🤖 **Adaptive Routing 2.3** (Hybrid + Quality):", file=sys.stderr)
    print(f"   ├─ Score: {score}/18 → Tier: {tier}", file=sys.stderr)
    print(f"   ├─ Provider: {provider_icon} {target_provider.upper()} ({routing_reason})", file=sys.stderr)
    print(f"   └─ Model: `{model_id}` [{model_reason}]", file=sys.stderr)
    if warning:
        print(f"\n{warning}", file=sys.stderr)

    log_routing_event(task_description, score, tier, model_id)

    return RoutingResult(
        model_id=model_id,
        tier=tier,
        provider=target_provider,
        score=score,
        warning=warning,
        pull_hints=pull_hints,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model Router 2.3 — Hybrid + Quality")
    parser.add_argument("task", help="Task description to route")
    parser.add_argument("--model", help="Manual model override")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON")
    args = parser.parse_args()

    result = route(args.task, args.model)

    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        print(result.model_id)
