#!/usr/bin/env python3
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe
from lib.llm_client import query_llm

ARENA_REPORTS_DIR = REPO_ROOT / ".agent" / "reports" / "arena"

DEFAULT_MODELS = [
    "qwen2.5-coder:32b",
    "codestral:22b",
    "qwen2.5-coder:14b"
]

JUDGE_MODEL = "qwen2.5-coder:32b"

def get_dynamic_duelists(prompt):
    """Dynamically resolves three dueling models based on prompt complexity."""
    try:
        from models.model_router import route, discover_ollama_url, get_ollama_local_models
        
        # 1. Route the prompt to find target model and tier
        result = route(prompt)
        print(f"🎯 Router Verdict: Tier [{result.tier}] -> Recommended model: `{result.model_id}`")
        
        # 2. Discover local models
        active_url, _ = discover_ollama_url("auto")
        local_models = get_ollama_local_models(active_url) if active_url else set()
        
        # If no local models, we fall back to standard cloud or defaults
        if not local_models:
            print("⚠️ No local Ollama models found. Using cloud defaults.")
            return [result.model_id], result.model_id
            
        # 3. Load rules to check alternatives
        rules_file = REPO_ROOT / ".agent" / "config" / "router_rules.json"
        rules = load_json_safe(rules_file)
        ollama_rules = rules.get("models", {}).get("ollama", {})
        
        # We want to select one model from each tier (L1, L2, L3) to compare,
        # fallback to alts if a tier's primary model is not pulled.
        selected_models = []
        
        for tier in ["L1", "L2", "L3"]:
            primary = ollama_rules.get(tier, "")
            alts = ollama_rules.get(f"{tier}_alt", [])
            candidates = [primary] + alts
            
            # Find first candidate actually pulled
            picked = None
            for c in candidates:
                if c in local_models:
                    picked = c
                    break
            
            if picked:
                selected_models.append(picked)
                
        # Ensure we always include the target model recommended by the router
        if result.model_id not in selected_models and result.model_id in local_models:
            selected_models.append(result.model_id)
            
        # Deduplicate while preserving order
        final_models = []
        for m in selected_models:
            if m not in final_models:
                final_models.append(m)
                
        # If we have less than 3 models, backfill with whatever is local
        if len(final_models) < 3:
            for m in local_models:
                if m not in final_models and "embed" not in m.lower():
                    final_models.append(m)
                if len(final_models) >= 3:
                    break
                    
        # The judge model should be the highest quality model among the duelists
        # or the target model itself. Let's pick the highest tier model available.
        judge = result.model_id
        for m in ["qwen2.5-coder:32b", "qwen3:30b", "qwen2.5-coder:14b"]:
            if m in final_models:
                judge = m
                break
                
        return final_models, judge
        
    except Exception as e:
        print(f"⚠️ Error resolving dynamic models: {e}")
        return DEFAULT_MODELS, JUDGE_MODEL

def run_duel(prompt, models=None):
    """Runs a duel between models for a given prompt."""
    judge_model = JUDGE_MODEL
    if models is None:
        models, judge_model = get_dynamic_duelists(prompt)
        
    ARENA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"🏟️ Starting True Arena Duel...")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  Dueling Models: {', '.join(models)}")
    
    responses = []
    
    for model in models:
        print(f"  🤖 Model: {model}...", end="", flush=True)
        response, stats = query_llm(prompt, model)
        responses.append({
            "model": model,
            "response": response,
            "stats": stats
        })
        print(" DONE")
        
    print(f"  ⚖️ Judging with {judge_model}...")
    
    judge_prompt = f"""You are the Multi-Agent Judge. 
We have a prompt and multiple responses from different models.
Your task: 
1. Analyze the responses.
2. Find common ground (consensus).
3. Identify unique insights from each.
4. Synthesize the FINAL BEST ANSWER.

PROMPT:
{prompt}

RESPONSES:
"""
    for i, r in enumerate(responses):
        judge_prompt += f"\n--- RESPONSE {i+1} (Model: {r['model']}) ---\n{r['response']}\n"
        
    final_answer, judge_stats = query_llm(judge_prompt, judge_model)
    
    # Save report using correct judge model
    report_path = save_arena_report(prompt, models, responses, final_answer)
    
    print("\n" + "="*40)
    print(f"📊 Duel Complete!")
    print(f"   Final Recommendation Generated.")
    print(f"   Report: {report_path}")
    print("="*40)
    
    print("\nFINAL SYNTHESIS:")
    print(final_answer)

def save_arena_report(prompt, models, responses, final_answer):
    """Saves the arena results to markdown."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = ARENA_REPORTS_DIR / f"duel_{timestamp}.md"
    
    with open(report_md, "w") as f:
        f.write(f"# True Arena Duel Report\n\n")
        f.write(f"- **Date**: {datetime.now().isoformat()}\n")
        f.write(f"- **Models Participated**: {', '.join(models)}\n\n")
        
        f.write(f"## Original Prompt\n\n> {prompt}\n\n")
        
        f.write("## Synthesis (Consensus)\n\n")
        f.write(final_answer + "\n\n")
        
        f.write("## Individual Responses\n\n")
        for r in responses:
            f.write(f"### Model: `{r['model']}`\n")
            f.write(f"- **Latency**: {r['stats'].get('elapsed_seconds', 0):.2f}s\n")
            f.write(f"- **TPS**: {r['stats'].get('tps', 0):.0f}\n")
            f.write("\n#### Response\n")
            f.write("```\n" + r['response'] + "\n```\n\n")
            
    return report_md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="True Arena - Multi-Model Duel Engine")
    parser.add_argument("prompt", help="Prompt to duel over")
    parser.add_argument("--models", nargs="+", help="Models to include in duel")
    args = parser.parse_args()
    
    run_duel(args.prompt, args.models)
