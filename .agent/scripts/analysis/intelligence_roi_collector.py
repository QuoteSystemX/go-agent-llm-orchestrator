
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

import json
from lib.metrics_base import MetricCollector
from lib.paths import TELEMETRY_PATH

class IntelligenceROICollector(MetricCollector):
    def __init__(self):
        super().__init__("Intelligence_ROI")

    def run(self):
        if not TELEMETRY_PATH.exists():
            self.add_metric("roi", "No Data", "WARN")
            self.save()
            return

        # Load dynamic local models from config
        from lib.paths import REPO_ROOT
        config_path = REPO_ROOT / ".agent" / "config" / "router_rules.json"
        local_models = set()
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    ollama_cfg = config.get("models", {}).get("ollama", {})
                    for tier_key in ["L1", "L2", "L3", "L4"]:
                        model = ollama_cfg.get(tier_key)
                        if model: local_models.add(model.lower())
                        for alt in ollama_cfg.get(f"{tier_key}_alt", []):
                            local_models.add(alt.lower())
            except:
                pass
        
        # Fallback prefixes if config loading fails or is incomplete
        if not local_models:
            local_models = {"qwen", "deepseek", "codestral", "ollama", "mistral", "gemma"}

        with open(TELEMETRY_PATH, "r") as f:
            data = json.load(f)

        events = data.get("events", [])
        if not events:
            self.add_metric("roi", "No Events", "WARN")
            self.save()
            return

        cloud_count = 0
        local_count = 0
        total_score = 0

        model_usage = {}

        for event in events:
            model_id = event.get("model_id", "").lower()
            if not model_id: continue
            
            total_score += event.get("score", 0)
            model_usage[model_id] = model_usage.get(model_id, 0) + 1

            # Check if it's a known local model or has a local prefix
            is_local = model_id in local_models or any(m in model_id for m in local_models)
            if is_local:
                local_count += 1
            else:
                cloud_count += 1

        total_calls = cloud_count + local_count
        local_ratio = (local_count / total_calls * 100) if total_calls > 0 else 0
        avg_complexity = (total_score / total_calls) if total_calls > 0 else 0

        self.add_metric("total_calls", total_calls)
        self.add_metric("local_calls", local_count)
        self.add_metric("cloud_calls", cloud_count)
        self.add_metric("local_ratio", f"{local_ratio:.1f}%")
        self.add_metric("avg_complexity", f"{avg_complexity:.1f}/20")
        
        # Determine ROI status (e.g., > 50% local is PASS)
        status = "PASS" if local_ratio > 50 else "WARN"
        self.add_metric("efficiency_score", f"{local_ratio:.1f}%", status)

        self.save()
        print(f"✅ Intelligence ROI: {local_ratio:.1f}% local (Avg Complexity: {avg_complexity:.1f})")

if __name__ == "__main__":
    IntelligenceROICollector().run()
